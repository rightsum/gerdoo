#!/usr/bin/env python3
"""Teensy 4.1 bring-up health check.

Runs a fixed battery against the bring-up firmware and exits non-zero if the
link is not healthy, so it can be wired into CI or called by an agent later.

Stdlib only — the Jetson has no pyserial, and the existing monitor.py already
drives the tty through termios directly.

Checks:
  1. port exists and opens
  2. PING -> PONG               link is alive
  3. INFO -> parsed             firmware identifies itself
  4. ECHO -> byte-exact         no corruption in either direction
  5. HEALTH -> parsed           temperature, restart cause, loop rate sane
  6. heartbeats (--monitor)     no gaps, no resets, steady cadence

Usage:
  python3 health_check.py --port /dev/ttyACM0
  python3 health_check.py --port /dev/ttyACM0 --monitor 30
  python3 health_check.py --port /dev/ttyACM0 --json
"""

import argparse
import json
import os
import random
import select
import string
import sys
import termios
import time

BAUD_MAP = {
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
    230400: termios.B230400,
    460800: termios.B460800,
}

# The firmware emits one heartbeat per second. Anything outside this band means
# the main loop is being starved or the board is resetting.
HEARTBEAT_MIN_S = 0.85
HEARTBEAT_MAX_S = 1.30

# i.MX RT1062 runs warm. Datasheet junction max is 95C; the chip throttles
# around 85C and panics near 95C. Under 70C idle is comfortable.
TEMP_WARN_C = 70.0
TEMP_FAIL_C = 85.0

# A bare loop with only serial polling should run in the tens of kHz. A much
# lower number means something is blocking.
LOOP_HZ_MIN = 1000


class Link:
    def __init__(self, port, baud):
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.old = termios.tcgetattr(self.fd)
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = 0  # iflag — no translation, no flow control
        attrs[1] = 0  # oflag
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0  # lflag — raw, no echo, no canonical mode
        speed = BAUD_MAP.get(baud, termios.B115200)
        attrs[4] = speed
        attrs[5] = speed
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        self.buf = b""

    def close(self):
        # A USB CDC port can vanish or refuse the restore if the board
        # re-enumerates mid-run. That is not a health failure, and it must not
        # mask the report we came here to produce.
        try:
            termios.tcsetattr(self.fd, termios.TCSANOW, self.old)
        except (termios.error, OSError):
            pass
        finally:
            try:
                os.close(self.fd)
            except OSError:
                pass

    def write_line(self, text):
        os.write(self.fd, (text + "\n").encode())

    def read_line(self, timeout):
        """Return one line, or None on timeout."""
        deadline = time.monotonic() + timeout
        while True:
            if b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                return line.decode("utf-8", "replace").strip()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            r, _, _ = select.select([self.fd], [], [], remaining)
            if not r:
                return None
            try:
                chunk = os.read(self.fd, 4096)
            except BlockingIOError:
                continue
            if chunk:
                self.buf += chunk

    def request(self, cmd, expect_tag, timeout=2.0):
        """Send a command, skip unsolicited heartbeats, return the reply."""
        self.write_line(cmd)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.read_line(deadline - time.monotonic())
            if line is None:
                return None
            if line.startswith(expect_tag):
                return line
            # HEARTBEAT/BOOT lines arrive unprompted; they are not failures.
        return None


def parse_kv(line):
    """'HEALTH temp_c=41.2 uptime_ms=5000' -> {'temp_c': '41.2', ...}"""
    out = {}
    for token in line.split()[1:]:
        if "=" in token:
            k, v = token.split("=", 1)
            out[k] = v
    return out


class Report:
    def __init__(self):
        self.checks = []
        self.data = {}

    def add(self, name, ok, detail):
        self.checks.append({"check": name, "ok": ok, "detail": detail})
        return ok

    @property
    def healthy(self):
        return all(c["ok"] for c in self.checks)

    def render(self):
        lines = []
        for c in self.checks:
            mark = "PASS" if c["ok"] else "FAIL"
            lines.append(f"  [{mark}] {c['check']:<22} {c['detail']}")
        return "\n".join(lines)


def run(port, baud, monitor_s, want_json):
    report = Report()

    if not os.path.exists(port):
        report.add("port exists", False,
                   f"{port} missing — board may still be in RawHID mode "
                   f"(check: lsusb | grep 16c0; want 0483, not 0486)")
        return report

    report.add("port exists", True, port)

    try:
        link = Link(port, baud)
    except OSError as exc:
        report.add("port opens", False, f"{exc} — check group 'dialout'")
        return report

    report.add("port opens", True, f"{baud} 8N1 raw")

    try:
        # The firmware talks continuously, so flush whatever is mid-line before
        # issuing the first command.
        link.read_line(0.3)

        t0 = time.monotonic()
        pong = link.request("PING", "PONG")
        rtt_ms = (time.monotonic() - t0) * 1000
        if pong:
            report.add("PING/PONG", True, f"{pong}  rtt={rtt_ms:.1f}ms")
        else:
            report.add("PING/PONG", False, "no reply in 2.0s — firmware not responding")
            return report

        info = link.request("INFO", "INFO")
        if info:
            kv = parse_kv(info)
            report.data["info"] = kv
            detail = (f"fw={kv.get('fw')} serial={kv.get('serial')} "
                      f"cpu={int(kv.get('cpu_hz', 0)) // 1000000}MHz")
            report.add("INFO", True, detail)
            report.add("USB mode", kv.get("usb") == "serial",
                       f"usb={kv.get('usb')} (want serial)")
        else:
            report.add("INFO", False, "no reply")

        payload = "".join(random.choices(string.ascii_letters + string.digits, k=64))
        echo = link.request(f"ECHO {payload}", "ECHO")
        if echo is None:
            report.add("ECHO round-trip", False, "no reply")
        else:
            got = echo[5:]
            report.add("ECHO round-trip", got == payload,
                       "64 bytes byte-exact" if got == payload
                       else f"corrupted: sent {payload!r} got {got!r}")

        health = link.request("HEALTH", "HEALTH")
        if health:
            kv = parse_kv(health)
            report.data["health"] = kv

            temp = float(kv.get("temp_c", "nan"))
            if temp != temp:  # NaN
                report.add("temperature", False, "unreadable")
            elif temp >= TEMP_FAIL_C:
                report.add("temperature", False, f"{temp:.1f}C — at/over throttle point")
            elif temp >= TEMP_WARN_C:
                report.add("temperature", True, f"{temp:.1f}C — warm, watch it")
            else:
                report.add("temperature", True, f"{temp:.1f}C")

            cause = kv.get("restart", "?")
            # power_on is the expected cause. watchdog/lockup/temp_panic mean
            # the board rebooted on its own, which USB re-enumeration hides.
            report.add("restart cause", cause in ("power_on", "jtag_sw"),
                       cause if cause in ("power_on", "jtag_sw")
                       else f"{cause} — board reset itself, not a clean boot")

            loop_hz = int(kv.get("loop_hz", 0))
            report.add("loop rate", loop_hz >= LOOP_HZ_MIN,
                       f"{loop_hz} Hz" + ("" if loop_hz >= LOOP_HZ_MIN
                                          else f" — below {LOOP_HZ_MIN}, loop is blocked"))
        else:
            report.add("HEALTH", False, "no reply")

        if monitor_s > 0:
            beats = []
            deadline = time.monotonic() + monitor_s
            while time.monotonic() < deadline:
                line = link.read_line(deadline - time.monotonic())
                if line and line.startswith("HEARTBEAT"):
                    beats.append((time.monotonic(), parse_kv(line)))

            if len(beats) < 2:
                report.add(f"heartbeat {monitor_s}s", False,
                           f"only {len(beats)} received — expected ~{monitor_s}")
            else:
                seqs = [int(b[1].get("seq", 0)) for b in beats]
                gaps = [seqs[i] - seqs[i - 1] for i in range(1, len(seqs))]
                intervals = [beats[i][0] - beats[i - 1][0] for i in range(1, len(beats))]
                worst = max(intervals)
                best = min(intervals)

                report.add("heartbeat continuity", all(g == 1 for g in gaps),
                           f"{len(beats)} beats, seq {seqs[0]}..{seqs[-1]}"
                           + ("" if all(g == 1 for g in gaps) else f" — GAPS: {gaps}"))
                report.add("heartbeat cadence",
                           HEARTBEAT_MIN_S <= best and worst <= HEARTBEAT_MAX_S,
                           f"min={best:.3f}s max={worst:.3f}s "
                           f"(want {HEARTBEAT_MIN_S}-{HEARTBEAT_MAX_S}s)")
                # seq restarting at 1 mid-run means the board rebooted.
                report.add("no resets", all(g >= 0 for g in gaps) and seqs[0] <= seqs[-1],
                           "sequence monotonic" if seqs[0] <= seqs[-1]
                           else "sequence went backwards — board rebooted")
    finally:
        link.close()

    return report


def main():
    ap = argparse.ArgumentParser(description="Teensy 4.1 bring-up health check")
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--monitor", type=float, default=0,
                    metavar="SEC", help="also watch heartbeats for SEC seconds")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    report = run(args.port, args.baud, args.monitor, args.json)

    if args.json:
        print(json.dumps({
            "healthy": report.healthy,
            "checks": report.checks,
            "data": report.data,
        }, indent=2))
    else:
        print(f"=== Teensy 4.1 health check — {args.port} ===")
        print(report.render())
        print()
        print("RESULT: HEALTHY" if report.healthy else "RESULT: UNHEALTHY")

    return 0 if report.healthy else 1


if __name__ == "__main__":
    sys.exit(main())
