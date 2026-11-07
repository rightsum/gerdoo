"""
Talking to the Teensy's console, correctly.

What this replaces spawned `cat` and `bash -c echo` per call, slept 450 ms, and
then returned the first buffered line that looked vaguely right — which was
usually the echo of an EARLIER command. It reported three different servo
positions in six seconds while nothing moved, and sent us chasing a fault that
did not exist.

The console is shared with a 1 Hz heartbeat, so any reply arrives interleaved
with unrelated output. The rules that make this reliable:

  * flush stale input BEFORE writing, so nothing already buffered can be
    mistaken for the answer,
  * read until a line matches what THIS command should return, ignoring
    heartbeats and anything else,
  * hold a lock, because two requests sharing one serial port interleave,
  * resolve the port by glob — the device path is not stable, and hardcoding a
    serial number has bitten this project three times.
"""

import glob
import os
import re
import termios
import threading
import time

PORT_GLOB = "/dev/serial/by-id/usb-Teensyduino_*Serial_*-if00"
BAUD = termios.B115200
TIMEOUT_S = 1.5

_lock = threading.Lock()


class TeensyError(RuntimeError):
    pass


def port_path():
    """The console device, by its stable by-id name. None if not plugged in."""
    found = sorted(glob.glob(PORT_GLOB))
    return found[0] if found else None


def _configure(fd):
    """Raw 115200, no echo — the same settings `stty raw -echo` would apply."""
    attrs = termios.tcgetattr(fd)
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = attrs
    iflag &= ~(termios.IXON | termios.IXOFF | termios.ICRNL | termios.INLCR)
    oflag &= ~termios.OPOST
    lflag &= ~(termios.ICANON | termios.ECHO | termios.ECHOE | termios.ISIG)
    cflag |= termios.CLOCAL | termios.CREAD
    cc[termios.VMIN] = 0
    cc[termios.VTIME] = 1          # 0.1 s read granularity
    termios.tcsetattr(fd, termios.TCSANOW,
                      [iflag, oflag, cflag, lflag, BAUD, BAUD, cc])


def send(cmd, expect, timeout=TIMEOUT_S):
    """
    Send one console command and return the first line matching `expect`.

    `expect` is a predicate on the line. Lines that do not match — heartbeats,
    log output, replies to something else — are skipped rather than returned.
    Returns None on timeout.
    """
    path = port_path()
    if not path:
        raise TeensyError("Teensy not connected")

    with _lock:
        fd = os.open(path, os.O_RDWR | os.O_NOCTTY)
        try:
            _configure(fd)
            # Anything already buffered predates this command and cannot be its
            # answer. This is the line whose absence caused the stale readings.
            termios.tcflush(fd, termios.TCIFLUSH)

            # A leading newline ends any half line left in the Teensy's buffer (an echo while
            # the port opens can leave one), so the command arrives on a line of its own.
            os.write(fd, ("\n" + cmd + "\n").encode())
            termios.tcdrain(fd)

            deadline = time.time() + timeout
            buf = b""
            while time.time() < deadline:
                try:
                    chunk = os.read(fd, 512)
                except BlockingIOError:
                    chunk = b""
                if not chunk:
                    time.sleep(0.02)
                    continue
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode("utf-8", "replace").strip()
                    if line and expect(line):
                        return line
            return None
        finally:
            os.close(fd)


_POS = re.compile(r"\b(pan|tilt)=(-?\d+)")


def parse_servo(line):
    """
    Pull pan/tilt out of a SERVO reply.

    Handles both "SERVO current pan=110 tilt=110" and "SERVO set pan=..." .
    Returns (pan, tilt), either of which may be None.
    """
    if not line:
        return None, None
    found = dict((k, int(v)) for k, v in _POS.findall(line))
    return found.get("pan"), found.get("tilt")


def is_servo_reply(line):
    """
    A line that actually reports a position.

    Bare `SERVO` prints usage FIRST and the position second:

        SERVO usage: SERVO pan=90 tilt=90  (0-180)
        SERVO current pan=110 tilt=110

    The usage line starts with "SERVO " and contains "pan=", so a looser test
    matches it and reports the example values 90/90 as the real position — which
    is exactly what happened before this was tightened.
    """
    return (line.startswith("SERVO current ") or line.startswith("SERVO set ")) \
        and ("pan=" in line or "tilt=" in line)


def servo_get():
    """Current neck target. Raises TeensyError if the board does not answer."""
    line = send("SERVO", is_servo_reply)
    if line is None:
        raise TeensyError("no reply from the Teensy")
    return parse_servo(line), line


def servo_set(pan=None, tilt=None):
    """Move the neck. Values are ints; the firmware clamps them to its limits."""
    parts = []
    if pan is not None:
        parts.append(f"pan={int(pan)}")
    if tilt is not None:
        parts.append(f"tilt={int(tilt)}")
    if not parts:
        raise ValueError("nothing to set")
    line = send("SERVO " + " ".join(parts), is_servo_reply)
    if line is None:
        raise TeensyError("no reply from the Teensy")
    return parse_servo(line), line


# ---- Arms (STS3215 bus servos through the Teensy: L = IDs 1-8, R = 11-18) ----

_ARM_COLS = re.compile(r"\b(pos|load|temp|seam|min|max|mt)=(-?\d+(?:,-?\d+)*)")
_ARM_STATE = re.compile(r"^ARM ([LR]) STATE ")


def parse_arm_state(line):
    """
    "ARM L STATE torque=1 speed=400 pos=a,b,... load=... temp=..." -> dict.

    None for anything else. A joint that did not answer reads -1 in every column.
    seam has a 1 for each joint the firmware's seam watchdog stopped since the
    previous STATE (each trip is reported once).
    """
    m = _ARM_STATE.match(line or "")
    if not m:
        return None
    torque = re.search(r"\btorque=(\d)", line)
    speed = re.search(r"\bspeed=(\d+)", line)
    strength = re.search(r"\bstrength=(\d+)", line)
    cols = {k: [int(x) for x in v.split(",")] for k, v in _ARM_COLS.findall(line)}
    return {
        "side": m.group(1),
        "torque": bool(torque and torque.group(1) == "1"),
        "speed": int(speed.group(1)) if speed else None,
        "strength": int(strength.group(1)) if strength else None,   # torque limit, 0-1000
        "pos": cols.get("pos", []),
        "load": cols.get("load", []),
        "temp": cols.get("temp", []),
        "seam": cols.get("seam", []),
        "min": cols.get("min", []),      # joint limits, kept in the Teensy's EEPROM
        "max": cols.get("max", []),
        "mt": cols.get("mt", []),        # 1 = servo in multi-turn mode (log 028)
    }


def _arm(side, cmd, reply_prefix, timeout=TIMEOUT_S):
    prefix = f"ARM {side} {reply_prefix}"
    line = send(f"ARM {side} {cmd}", lambda l: l.startswith(prefix), timeout=timeout)
    if line is None:
        raise TeensyError("no reply from the Teensy")
    return line


def arm_state(side):
    line = _arm(side, "STATE", "STATE ")
    return parse_arm_state(line), line


def arm_torque(side, on):
    """Enable (goal = present position first, so nothing jumps) or release."""
    return _arm(side, "TORQUE " + ("ON" if on else "OFF"), "TORQUE ", timeout=3)


def arm_speed(side, steps_per_s):
    """Goal speed for that arm's later moves, in steps/s. The firmware clamps 50-3000."""
    return int(_arm(side, f"SPEED {int(steps_per_s)}", "SPEED ").split()[3])


def arm_strength(side, limit):
    """Torque limit (100-1000) for every joint of the arm, applied immediately."""
    return int(_arm(side, f"STRENGTH {int(limit)}", "STRENGTH ").split()[3])


def arm_calibrate(side, joint, mid, half_span):
    """
    Make the middle of a joint's hand-recorded range read 2048 and store its
    limits in the servo. The reply contains " ok " only if the firmware saw
    the reading move as expected; otherwise it restored the old values.
    """
    return _arm(side, f"CALIBRATE {int(joint)} {int(mid)} {int(half_span)}", "CALIBRATE ", timeout=3)


def arm_move(side, joint, pos):
    """Returns the firmware's reply; it ends in " ok" only if the write landed."""
    return _arm(side, f"MOVE {int(joint)} {int(pos)}", "MOVE ")


# ---- Light: the COB strip, following the photoresistor or set by hand ----

_LIGHT = re.compile(r"^LIGHT raw=(\d+) norm=([\d.]+) cal_dark=(\d+) cal_bright=(\d+) "
                    r"duty=(\d+)/(\d+).* mode=(auto|manual)(?: level=(-?[\d.]+))?")


def parse_light(line):
    """
    "LIGHT raw=3022 norm=1.000 cal_dark=529 cal_bright=1400 duty=38/4095
    (cap of 4095) mode=auto level=-1.00" -> dict. None for anything else.

    sensor is 0 (dark room) .. 1 (bright room) between the two calibration
    readings; duty is what is on the strip's pin now. level is the manual
    setting 0..1, None in auto (older firmware does not print it).
    """
    m = _LIGHT.match(line or "")
    if not m:
        return None
    raw, norm, dark, bright, duty, duty_max, mode, level = m.groups()
    lvl = float(level) if level is not None else None
    return {
        "sensor_raw": int(raw), "sensor": float(norm),
        "cal_dark": int(dark), "cal_bright": int(bright),
        "duty": int(duty), "duty_max": int(duty_max),
        "mode": mode, "level": lvl if lvl is not None and lvl >= 0 else None,
    }


def light_state():
    line = send("LIGHT", lambda l: l.startswith("LIGHT raw="))
    if line is None:
        raise TeensyError("no reply from the Teensy")
    return parse_light(line), line


def light_set(level):
    """level 0-100 for a fixed brightness, or None to follow the light sensor."""
    line = send("STRIP auto" if level is None else f"STRIP {int(level)}",
                lambda l: l.startswith("STRIP mode="))
    if line is None:
        raise TeensyError("no reply from the Teensy")
    return line


def light_calibrate(which):
    """Record the sensor's reading now as the 'dark' or 'bright' end (until the next reboot)."""
    line = send(f"CAL {which}", lambda l: l.startswith(f"CAL {which}="))
    if line is None:
        raise TeensyError("no reply from the Teensy")
    return int(line.split("=")[1])


# ---- Drive motors and ultrasonic sensors (log 046) ----

_DRIVE_COLS = re.compile(r"\b(run|duty|enc|sonar)=(-?[\d.]+(?:,-?[\d.]+)*)")
SONAR_NAMES = ("FL", "FR", "BL", "BR")
_SONAR_CODES = {-1: "far", -2: "silent", -3: "waiting"}


def parse_drive_state(line):
    """
    "DRIVE run=0,1 duty=0,15 enc=-395,351 sonar=12.8,-1,-2,-3" -> dict.

    None for anything else. Sonar: centimetres, or -1 = nothing in range (far),
    -2 = no echo pulse at all (power or wiring: silent), -3 = not read yet.
    Duty is the percentage on the pins now, signed: + is the bridge's RPWM side.
    """
    if not (line or "").startswith("DRIVE run="):
        return None
    cols = {k: v.split(",") for k, v in _DRIVE_COLS.findall(line)}
    run, duty, enc = cols.get("run", []), cols.get("duty", []), cols.get("enc", [])
    motors = {}
    for i, side in enumerate(("L", "R")):
        motors[side] = {
            "running": i < len(run) and run[i] == "1",
            "duty": int(duty[i]) if i < len(duty) else None,
            "enc": int(enc[i]) if i < len(enc) else None,
        }
    sonar = {}
    for name, raw in zip(SONAR_NAMES, cols.get("sonar", [])):
        v = float(raw)
        sonar[name] = ({"state": "ok", "cm": v} if v >= 0
                       else {"state": _SONAR_CODES.get(int(v), "waiting"), "cm": None})
    return {"motors": motors, "sonar": sonar}


def drive_state():
    line = send("DRIVE", lambda l: l.startswith("DRIVE run="))
    if line is None:
        raise TeensyError("no reply from the Teensy")
    return parse_drive_state(line), line


def motor_run(side, percent, ms):
    """
    One timed run; the firmware stops it by itself after `ms`. It refuses more
    than 30 % or 3000 ms, which comes back as "MOTOR ERR ...".
    """
    line = send(f"MOTOR {side} {int(percent)} {int(ms)}",
                lambda l: l.startswith(f"MOTOR {side} start") or l.startswith("MOTOR ERR"))
    if line is None:
        raise TeensyError("no reply from the Teensy")
    return line


def motor_stop():
    line = send("MOTOR STOP", lambda l: l == "MOTOR stopped")
    if line is None:
        raise TeensyError("no reply from the Teensy")
    return line


def encoders_zero():
    line = send("ENC ZERO", lambda l: l.startswith("ENC L="))
    if line is None:
        raise TeensyError("no reply from the Teensy")
    return line
