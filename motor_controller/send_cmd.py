#!/usr/bin/env python3
"""Send serial commands to the motor controller."""
import os, select, sys, termios, time

def open_tty(port, baud):
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[0] = 0
    new[1] = 0
    new[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    new[3] = 0
    bauds = {9600: termios.B9600, 19200: termios.B19200,
             38400: termios.B38400, 57600: termios.B57600,
             115200: termios.B115200}
    b = bauds.get(baud, termios.B9600)
    new[4] = b
    new[5] = b
    termios.tcsetattr(fd, termios.TCSANOW, new)
    return fd, old

def send_cmd(port, baud, cmd):
    fd, old = open_tty(port, baud)
    try:
        # Arduino resets on port open — wait for boot to finish
        time.sleep(2.5)
        # Drain any boot output
        end = time.time() + 1.0
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                try: os.read(fd, 256)
                except OSError: break

        os.write(fd, (cmd + "\n").encode())
        time.sleep(0.3)  # give Arduino time to respond
        data = b""
        end = time.time() + 2.0
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], 0.3)
            if r:
                try:
                    chunk = os.read(fd, 256)
                    if chunk: data += chunk
                except OSError: break
        sys.stdout.buffer.write(data)
        sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, old)
        os.close(fd)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Send commands to motor controller")
    parser.add_argument("port", help="Serial port")
    parser.add_argument("cmd", help="Command string to send (e.g. F, B, L, S)")
    parser.add_argument("-b", "--baud", type=int, default=9600)
    args = parser.parse_args()
    send_cmd(args.port, args.baud, args.cmd)
