#!/usr/bin/env python3
"""Demo script: send a sequence of motor commands."""
import os, select, sys, termios, time

PORT = '/dev/cu.usbserial-410'
BAUD = 9600

fd = os.open(PORT, os.O_RDWR | os.O_NOCTTY)
old = termios.tcgetattr(fd)
new = termios.tcgetattr(fd)
new[0] = 0; new[1] = 0
new[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
new[3] = 0
b = termios.B9600
new[4] = b; new[5] = b
termios.tcsetattr(fd, termios.TCSANOW, new)

def read_all(timeout=2.0):
    end = time.time() + timeout
    data = b""
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            try:
                chunk = os.read(fd, 256)
                if chunk: data += chunk
            except OSError:
                break
    return data.decode('utf-8', errors='replace')

def send(cmd):
    os.write(fd, (cmd + "\n").encode())

try:
    # After opening, board resets — wait for boot messages
    time.sleep(2.5)
    print(read_all(0.5))

    print("\n--- Sending demo commands ---")

    send("F 180")
    print(read_all(0.8))

    send("S")
    print(read_all(0.5))

    send("L 200")
    print(read_all(0.8))

    send("S")
    print(read_all(0.5))

    send("R 200")
    print(read_all(0.8))

    send("S")
    print(read_all(0.5))

    send("B 150")
    print(read_all(0.8))

    send("S")
    print(read_all(0.5))

    print("--- Demo done ---")

finally:
    termios.tcsetattr(fd, termios.TCSANOW, old)
    os.close(fd)
