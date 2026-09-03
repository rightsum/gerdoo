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

            os.write(fd, (cmd + "\n").encode())
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
