#!/usr/bin/env python3
"""Simple serial monitor for Arduino."""
import os
import select
import sys
import termios
import time

def open_tty(port: str, baud: int):
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    # raw-ish mode, 8N1
    new[0] = 0  # iflag
    new[1] = 0  # oflag
    new[2] = termios.CS8 | termios.CREAD | termios.CLOCAL  # cflag
    new[3] = 0  # lflag
    # Speeds: map common baud rates
    baud_rates = {
        9600: termios.B9600,
        19200: termios.B19200,
        38400: termios.B38400,
        57600: termios.B57600,
        115200: termios.B115200,
    }
    b = baud_rates.get(baud, termios.B9600)
    new[4] = b  # ispeed
    new[5] = b  # ospeed
    termios.tcsetattr(fd, termios.TCSANOW, new)
    return fd, old

def monitor(port: str, baud: int, duration: float = None):
    fd, old = open_tty(port, baud)
    # Wait a moment for board reset and data
    time.sleep(0.5)
    try:
        end = time.time() + duration if duration else None
        while True:
            if end and time.time() >= end:
                break
            timeout = 0.5 if end is None else min(0.5, end - time.time())
            if timeout <= 0:
                break
            r, _, _ = select.select([fd], [], [], timeout)
            if r:
                try:
                    chunk = os.read(fd, 256)
                    if chunk:
                        sys.stdout.buffer.write(chunk)
                        sys.stdout.flush()
                except OSError:
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, old)
        os.close(fd)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Serial monitor for Arduino")
    parser.add_argument("port", help="Serial port (e.g. /dev/cu.usbserial-410)")
    parser.add_argument("-b", "--baud", type=int, default=9600, help="Baud rate")
    parser.add_argument("-d", "--duration", type=float, default=None,
                        help="Read for N seconds then exit")
    args = parser.parse_args()
    monitor(args.port, args.baud, args.duration)
