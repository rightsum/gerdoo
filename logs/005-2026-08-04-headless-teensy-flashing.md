# 005 — Headless Teensy flashing with `teensy_loader_cli`

| | |
|---|---|
| **Date** | 2026-08-04 |
| **Type** | Dependency removal |
| **Status** | ✅ Done — flashing works with `DISPLAY` unset |
| **Closes** | ACTION-PLAN **C7** |
| **Follows** | [Log 003](003-2026-08-04-teensy-rawhid-bringup.md), which left this as the last fragile step |

---

## Problem

After [log 003](003-2026-08-04-teensy-rawhid-bringup.md) the Teensy flashed fine, but only through a chain ending in a GUI:

```
make upload → arduino-cli upload → teensy_post_compile → Teensy Loader (GTK app)
```

`teensy_post_compile` **does not flash anything**. It messages the Teensy Loader *application*, which does the work. That app is GTK:

```
$ teensy --help
Error: Unable to initialize GTK+, is DISPLAY set properly?
```

It worked only because the Jetson happened to have a live X session, so a background process was parked on `DISPLAY=:0`.

### Why that was unacceptable

1. **It dies with the desktop session.** Any logout, gdm restart, or display fault silently breaks firmware flashing — on a robot, discovered at the worst moment.
2. **A robot has no business needing a desktop to update its own firmware.**
3. **The window was invisible anyway.** The panel runs the `robot-face` kiosk full-screen ([log 006](006-2026-08-04-robot-face-adoption.md)), so the loader window sat behind it. When its status line was reported as *"Press button on Teensy to manually enter program mode"*, that was its permanent idle text — not a prompt, and not actually visible on the panel.

## Fix

`teensy_loader_cli` — PJRC's standalone flasher. Talks USB directly, no GUI, no `DISPLAY`.

Not packaged for Ubuntu; built from source:

```bash
sudo apt install libusb-dev          # the 0.1 API — provides /usr/include/usb.h
mkdir -p ~/src && cd ~/src
git clone --depth 1 https://github.com/PaulStoffregen/teensy_loader_cli.git
cd teensy_loader_cli && make
install -m 0755 teensy_loader_cli ~/.local/bin/
```

Built clean first try:

```
cc -O2 -Wall -s -DUSE_LIBUSB -o teensy_loader_cli teensy_loader_cli.c -lusb
```

| | |
|---|---|
| Version | Teensy Loader, Command Line, 2.3 |
| Commit | `03fca4156c244c7ad36bd368cf6e24531dbd566a` (2024-02-27) |
| Built against | `libusb-dev` 2:0.1.12-32build3 |
| Installed | `~/.local/bin/teensy_loader_cli` (no sudo) |

**Note the libusb version.** It links `-lusb` (libusb **0.1**), not libusb-1.0. `/usr/include/libusb-1.0/libusb.h` is absent on this machine and that is fine — `libusb-dev` is the 0.1 development package and is the right one.

## Verification

The test that matters: kill the GUI loader, unset `DISPLAY` **and** `XAUTHORITY`, flash.

```bash
kill $(pgrep -f "teensy-tools/1.62.0/teensy$")

env -u DISPLAY -u XAUTHORITY bash -c '
  teensy_loader_cli --mcu=TEENSY41 -w -s -v build/teensy_bringup.ino.hex'
```

```
DISPLAY is: []
Teensy Loader, Command Line, Version 2.3
Read "build/teensy_bringup.ino.hex": 25600 bytes, 0.3% usage
Soft reboot performed
Waiting for Teensy device...
 (hint: press the reset button)
Found HalfKay Bootloader
Programming......................
Booting
```

Board came back as `16c0:0483` with the by-id symlink intact, then a full `make monitor`:

```
RESULT: HEALTHY        (12/12 — RTT 0.2ms, loop 7.06 MHz, restart power_on,
                        heartbeat 1.000s min and max, 54.6C)
```

**Still no button press.** `-s` soft-reboots a running board into its bootloader over USB. That works *only because the PJRC udev rules from log 003 are installed* — without them the bootloader is root-only and the tool waits forever behind the misleading `(hint: press the reset button)`. Recorded in the Makefile so it is not rediscovered.

Hex is **25,600 bytes, 0.3 % of flash** — ample headroom for micro-ROS, which is not small.

## Makefile changes

| Before | After |
|---|---|
| `arduino-cli upload` | `teensy_loader_cli --mcu=TEENSY41 -w -s -v` |
| `loader` target starting a GTK app | **deleted** |
| `export DISPLAY` / `XAUTHORITY` | **deleted** |
| `UPLOAD_PORT` from `arduino-cli board list` | **deleted** — the CLI loader finds the board itself |

`arduino-cli` still compiles. It just no longer touches flashing.

`timeout 90` wraps the flash so `-w` (wait for device) cannot hang a build forever.

## Consequences

- **Firmware pipeline no longer depends on a desktop session.** Compile and flash work over a bare SSH connection — including the USB fallback link (`192.168.55.1`) when wifi is down.
- **The GUI loader window is gone permanently**, not just closed.
- **`teensy_loader_cli` is not apt-managed.** It will not update with the system, and it lives only in `~/.local/bin` on this Jetson. **After any OS reflash it must be rebuilt** — clone is kept at `~/src/teensy_loader_cli`, so `make && install -m 0755 teensy_loader_cli ~/.local/bin/`.

## Takeaways

1. **`teensy_post_compile` is not a flasher.** It is an IPC message to a GUI app. On headless hardware, `teensy_loader_cli` is the only sane path.
2. **`libusb-dev` (0.1) ≠ `libusb-1.0-0-dev`.** The 0.1 package is correct here; a missing `libusb-1.0/libusb.h` is not a problem.
3. **`-s` depends on udev rules.** Without them the failure looks like a hardware problem ("press the reset button") rather than a permissions one.
4. **A GUI dependency on a headless machine is a latent outage**, even when it currently works.

## Related

- [003](003-2026-08-04-teensy-rawhid-bringup.md) — Teensy bring-up; udev rules that make `-s` work
- [006](006-2026-08-04-robot-face-adoption.md) — the kiosk that made the loader window invisible
- [`../ACTION-PLAN.md`](../ACTION-PLAN.md) item C7
