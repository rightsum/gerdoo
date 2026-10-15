"""Send one line to the Teensy's human console and print the matching replies.

    python3 console.py "BUS SCAN 7" 30          # read-only: who is on the servo bus
    python3 console.py "BUS SETID 1 11" 5        # the only write: change one servo's ID
    python3 console.py "ARM R STATE" 3 ARM      # one arm's positions, load, temperature

Only lines starting with the prefix (default: the command's first word) are
printed, so the 1 Hz heartbeat does not bury the answer. A scan ends early on
its "done" line.

Nothing else may be reading the console at the same time. The control panel's
arm cards poll it and flush its input on every poll, which silently eats
replies meant for this script. Close the cards first.
"""
import glob
import os
import select
import sys
import termios
import time
import tty

PORT_GLOB = "/dev/serial/by-id/usb-Teensyduino_*Serial_*-if00"


def main():
    cmd = sys.argv[1]
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 5
    prefix = sys.argv[3] if len(sys.argv) > 3 else cmd.split()[0]
    ports = sorted(glob.glob(PORT_GLOB))
    if not ports:
        sys.exit("Teensy console not found: " + PORT_GLOB)

    fd = os.open(ports[0], os.O_RDWR | os.O_NOCTTY)
    tty.setraw(fd)
    termios.tcflush(fd, termios.TCIFLUSH)
    os.write(fd, (cmd + "\n").encode())

    buf = b""
    end = time.time() + secs
    while time.time() < end:
        ready, _, _ = select.select([fd], [], [], 0.2)
        if not ready:
            continue
        buf += os.read(fd, 4096)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            text = line.decode(errors="replace").strip()
            if text.startswith(prefix) or text.startswith("ERR"):
                print(text, flush=True)
                if " SCAN done" in text:
                    end = 0
    os.close(fd)


if __name__ == "__main__":
    main()
