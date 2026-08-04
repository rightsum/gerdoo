#!/usr/bin/env python3
"""
Real-time keyboard control for the motor controller.

Controls (press and hold):
  W      Forward
  S      Backward
  A      Turn Left  (spin in place)
  D      Turn Right (spin in place)
  Space  Stop
  Q      Quit

  +      Increase speed by 25
  -      Decrease speed by 25

The motor stops automatically ~300 ms after you release a key.
"""
import glob
import os
import select
import sys
import termios
import time
import tty

# Auto-detect serial port: prefer usbserial (Nano/CH340) over usbmodem
_ports = glob.glob('/dev/cu.usbserial*')
if not _ports:
    _ports = glob.glob('/dev/cu.usbmodem*')
if not _ports:
    print("ERROR: No Arduino serial port found. Is the Nano plugged in?")
    sys.exit(1)
PORT = _ports[0]
BAUD = 9600
STOP_TIMEOUT = 0.3  # seconds before auto-stop when no key held

# ---------------------------------------------------------------------------
# Serial helpers (raw termios, no pyserial dependency)
# ---------------------------------------------------------------------------

def open_serial(port, baud):
    # macOS: reset port with stty first to avoid Invalid argument from termios
    os.system(f"stty -f {port} {baud} cs8 -cstopb -parenb raw -echo 2>/dev/null")
    time.sleep(0.05)

    fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[0] = 0  # iflag
    new[1] = 0  # oflag
    new[2] = termios.CS8 | termios.CREAD | termios.CLOCAL  # cflag
    new[3] = 0  # lflag
    bauds = {
        9600: termios.B9600, 19200: termios.B19200,
        38400: termios.B38400, 57600: termios.B57600,
        115200: termios.B115200,
    }
    b = bauds.get(baud, termios.B9600)
    new[4] = b
    new[5] = b
    try:
        termios.tcsetattr(fd, termios.TCSANOW, new)
    except termios.error:
        # macOS USB serial sometimes rejects tcsetattr; stty already configured it
        pass
    return fd, old


def drain(fd, timeout=1.0):
    """Read and discard anything on the wire (used after open/reset)."""
    end = time.time() + timeout
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try:
                os.read(fd, 256)
            except OSError:
                break


def read_available(fd):
    """Non-blocking read every pending byte."""
    data = b""
    while True:
        r, _, _ = select.select([fd], [], [], 0.0)
        if not r:
            break
        try:
            chunk = os.read(fd, 256)
            if not chunk:
                break
            data += chunk
        except OSError:
            break
    return data.decode('utf-8', errors='replace')


# ---------------------------------------------------------------------------
# Keyboard helpers
# ---------------------------------------------------------------------------

def set_raw(stdin_fd):
    old = termios.tcgetattr(stdin_fd)
    tty.setraw(stdin_fd, termios.TCSANOW)
    return old


def getch(stdin_fd, timeout=0.05):
    """Non-blocking single character read."""
    r, _, _ = select.select([stdin_fd], [], [], timeout)
    if r:
        return sys.stdin.read(1)
    return None


# ---------------------------------------------------------------------------
# Main control loop
# ---------------------------------------------------------------------------

def main():
    ser_fd, ser_old = open_serial(PORT, BAUD)
    stdin_fd = sys.stdin.fileno()
    stdin_old = set_raw(stdin_fd)

    # Arduino resets when port opens — wait for boot messages to finish
    print("Waiting for Arduino to boot...")
    time.sleep(2.5)
    drain(ser_fd, timeout=1.0)
    print("Ready. Controls: W=forwards  S=backwards  A=left  D=right  Space=stop  Q=quit\n")

    speed = 200
    last_cmd = None
    last_cmd_time = 0.0

    # Clear screen once using ANSI escape codes
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

    print(f"Connected on {PORT}\n")
    try:
        while True:
            now = time.time()

            # ---- Read keyboard input (non-blocking) ----
            ch = getch(stdin_fd, timeout=0.02)
            cmd = None

            if ch is not None:
                c = ch.lower()
                if c == 'w':
                    cmd = f"F {speed}"
                elif c == 's':
                    cmd = f"B {speed}"
                elif c == 'a':
                    cmd = f"L {speed}"
                elif c == 'd':
                    cmd = f"R {speed}"
                elif ch == ' ':
                    cmd = "S"
                elif c == 'q':
                    raise SystemExit
                elif c == 'p':
                    cmd = "P"
                elif c == 'i':
                    cmd = "I"
                elif c == 't':
                    cmd = "D"
                elif ch == '+':
                    speed = min(255, speed + 25)
                    cmd = None
                    if last_cmd and last_cmd[0] in ('F','B','L','R'):
                        prefix = last_cmd[0]
                        cmd = prefix + " " + str(speed)
                elif ch == '-':
                    speed = max(0, speed - 25)
                    cmd = None
                    if last_cmd and last_cmd[0] in ('F','B','L','R'):
                        prefix = last_cmd[0]
                        cmd = prefix + " " + str(speed)
                elif c == 'h':
                    cmd = "H"

                if cmd:
                    last_cmd = cmd
                    last_cmd_time = now
                    os.write(ser_fd, (cmd + "\n").encode())

            # ---- Auto-stop if key released for STOP_TIMEOUT ----
            if last_cmd and last_cmd != "S" and (now - last_cmd_time) > STOP_TIMEOUT:
                last_cmd = "S"
                os.write(ser_fd, b"S\n")

            # ---- Read and print serial responses ----
            resp = read_available(ser_fd)
            if resp:
                # Drop stale boot noise if any
                lines = resp.strip().splitlines()
                for line in lines:
                    line = line.strip()
                    if line and "Motor Controller Help" not in line and "=" not in line:
                        # Overwrite status line with motor response
                        sys.stdout.write(f"\r\033[K{line}\n")
                        sys.stdout.flush()

            # ---- Redraw status line ----
            status = f"[Speed: {speed:3d} | Last: {last_cmd or '---':8s} | W/A/S/D=move Space=stop P=pan I=tilt T=diag Q=quit]"
            sys.stdout.write(f"\r\033[K{status}")
            sys.stdout.flush()

            time.sleep(0.02)

    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        # Send stop before exiting
        try:
            os.write(ser_fd, b"S\n")
        except OSError:
            pass
        termios.tcsetattr(stdin_fd, termios.TCSANOW, stdin_old)
        termios.tcsetattr(ser_fd, termios.TCSANOW, ser_old)
        os.close(ser_fd)
        print("\n\nStopped and disconnected.")


if __name__ == "__main__":
    main()
