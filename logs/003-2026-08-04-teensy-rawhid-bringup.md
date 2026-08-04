# 003 — Teensy 4.1 bring-up: RawHID mode, headless flashing, unstable port

| | |
|---|---|
| **Date opened** | 2026-08-03 |
| **Date resolved** | 2026-08-04 |
| **Status** | ✅ Fixed — board healthy, 12/12 checks pass |
| **Severity** | High — no serial link between Jetson and Teensy at all |
| **Hardware** | Teensy 4.1 (i.MX RT1062), serial `19627940`, on Jetson Orin Nano USB `1-2.4` |
| **Artifacts** | `teensy_bringup/{teensy_bringup.ino,Makefile,health_check.py}` |

---

## Symptom

Teensy plugged into the Jetson, LED blinking, but no serial device anywhere:

```
$ ls /dev/ttyACM* /dev/ttyUSB*
ls: cannot access '/dev/ttyACM*': No such file or directory
ls: cannot access '/dev/ttyUSB*': No such file or directory
```

## Root cause #1 — wrong USB type

```
$ lsusb | grep 16c0
Bus 001 Device 008: ID 16c0:0486 Van Ooijen Technische Informatica Teensyduino RawHID
```

`16c0:0486` is **RawHID**. Serial is `16c0:0483`.

The firmware had been built with **USB Type = "Raw HID"**, so the board offers **no CDC interface at all**. No amount of driver or permission work can produce a serial node from it — the device simply does not present one. Confirmed in sysfs:

```
iface 0  class=03 (HID)  driver=usbhid
iface 1  class=03 (HID)  driver=usbhid
```

Everything else was healthy: enumerated at `1-2.4`, 480 Mbps (correct for Teensy 4.1), power `active`, no reset loop. **Not a cable, power, or solder fault.** The blinking LED meant a sketch was running fine — it just couldn't be talked to.

### Secondary access problem

Even in RawHID the board was unreachable as a normal user:

```
crw------- 1 root root  /dev/hidraw0
crw------- 1 root root  /dev/hidraw2
```

`jarvis` is in `dialout` and `plugdev`, but **neither group covers `hidraw`**, and no PJRC udev rule was installed. So RawHID wasn't even usable *as* RawHID.

## Fix #1 — rebuild as Serial, pinned in the FQBN

```
teensy:avr:teensy41:usb=serial,speed=600,opt=o2std,keys=en-us
```

`usb=serial` is pinned in the Makefile's FQBN, not left to a default. This is the entire bug, and leaving it implicit is how it recurs.

Serial mode also fixes access as a side effect: `/dev/ttyACM*` is created `root:dialout 660`, and `jarvis` is already in `dialout`. **No udev rule is needed for normal operation** — only for flashing (below).

## Root cause #2 — flashing needs udev rules *and* a GUI

Two separate obstacles, hit in sequence.

**First**, `arduino-cli upload` failed with `no upload port provided`. The Makefile was looking for `/dev/ttyACM*` to pass as the port — which **cannot exist while the board is in RawHID**. Circular.

The real address comes from arduino-cli's Teensy discovery protocol, which works regardless of USB mode:

```
$ arduino-cli board list
Port           Protocol Type         Board Name  FQBN
usb1/1-2/1-2.4 teensy   Teensy Ports Teensy 4.1  teensy:avr:teensy41
```

**Second**, with the right port it still failed:

```
Unable find Teensy Loader.  (p)  Is the Teensy Loader application running?
```

`teensy_post_compile` **does not flash anything**. It notifies the Teensy Loader *application*, which does the actual work. That app is GTK:

```
$ teensy --help
Error: Unable to initialize GTK+, is DISPLAY set properly?
```

A genuine headless problem. Options were: install `teensy_loader_cli` (needs `libusb-dev`, and `sudo`), run `Xvfb` (not installed), or use the display already present.

The Jetson turned out to have a live session:

```
$ who
jarvis   :0    2026-08-02 21:08 (:0)
```

## Fix #2 — udev rules, then the loader on `:0`

The core ships the rules file, so nothing needed downloading. Note the **absolute path** — `~` expands to `/root` under sudo, which is how the first attempt failed:

```bash
sudo cp /home/jarvis/.arduino15/packages/teensy/tools/teensy-tools/1.62.0/00-teensy.rules \
        /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Effect was immediate and visible — `hidraw` went world-accessible:

```
crw-rw-rw- 1 root root  /dev/hidraw0     (was crw-------)
```

Then the loader against the existing display:

```bash
export DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority
nohup ~/.arduino15/packages/teensy/tools/teensy-tools/1.62.0/teensy &
```

All three `XAUTHORITY` candidates worked (`/run/user/1000/gdm/Xauthority`, `~/.Xauthority`, none), so access was not the constraint — only the missing `DISPLAY`.

### No PROGRAM button needed

Expectation was that the first flash would require pressing the physical button, since `teensy_reboot` cannot reach a RawHID device without udev rules. **Once the rules were installed it soft-rebooted the board into its bootloader over HID.** The board was never physically touched. Every later flash works the same way — no physical access to the robot required.

```
found Teensy Loader, version 1.62
Sending command: show:arduino_attempt_reboot
```

Result:

```
Bus 001 Device 010: ID 16c0:0483 Van Ooijen Technische Informatica Teensyduino Serial
crw-rw-rw- 1 root dialout 166, 0  /dev/ttyACM0
```

## Root cause #3 — the serial node is not stable

Between two consecutive health-check runs, with **nothing unplugged and no reboot**, the port moved:

```
run 1:  /dev/ttyACM0     (device 010)
run 2:  /dev/ttyACM1     (device 012)
run 3:  /dev/ttyACM0     (device 014)   ← moved back
```

It moves in **both directions**, purely from USB re-enumeration on flash. Anything hardcoding `/dev/ttyACM0` breaks unpredictably — after a reflash, a brownout, or a reboot. This is a latent robot-breaking bug, found only because the numbering happened to shift mid-session.

## Fix #3 — address the board by serial number

```
/dev/serial/by-id/usb-Teensyduino_USB_Serial_19627940-if00
```

Created automatically once the board is in Serial mode; it tracked every re-enumeration correctly. `19627940` is the Teensy's own serial number, so this **also disambiguates boards** once a second Teensy is added for the arm.

**Rule: never hardcode `/dev/ttyACM<N>` anywhere — Makefile, ROS launch files, or firmware tooling.**

## Verification

```
=== Teensy 4.1 health check — /dev/serial/by-id/usb-Teensyduino_USB_Serial_19627940-if00 ===
  [PASS] port exists            /dev/serial/by-id/usb-Teensyduino_USB_Serial_19627940-if00
  [PASS] port opens             115200 8N1 raw
  [PASS] PING/PONG              PONG 20269  rtt=0.2ms
  [PASS] INFO                   fw=bringup-0.1.0 serial=1962794 cpu=600MHz
  [PASS] USB mode               usb=serial (want serial)
  [PASS] ECHO round-trip        64 bytes byte-exact
  [PASS] temperature            54.0C
  [PASS] restart cause          power_on
  [PASS] loop rate              7058454 Hz
  [PASS] heartbeat continuity   10 beats, seq 18..27
  [PASS] heartbeat cadence      min=1.000s max=1.000s (want 0.85-1.3s)
  [PASS] no resets              sequence monotonic

RESULT: HEALTHY
```

| Measurement | Value | Reading |
|---|---|---|
| Round-trip latency | **0.2 ms** | ample margin for a control loop |
| Loop rate | **7.06 MHz** | nothing blocking in `loop()` |
| Restart cause | **`power_on`** | clean boot — not watchdog, lockup, or temp panic |
| Heartbeat cadence | **1.000 s** min *and* max over 10 beats | `millis()` timing solid |
| Temperature | **54.0 °C** idle | 31 °C below the 85 °C throttle point. Warm but normal for 600 MHz with no airflow — **recheck once enclosed** |
| ECHO | 64 bytes byte-exact | no corruption either direction |

Build: FLASH code 13,100 B (8.1 MB free), RAM1 486 KB free for locals, RAM2 512 KB free.

## Toolchain installed

Jetson is aarch64 Ubuntu 22.04, and PJRC ships a full `aarch64-linux-gnu` toolchain, so everything builds natively on the robot — no laptop in the loop.

| Component | Version | Location |
|---|---|---|
| arduino-cli | 1.5.2-rc.1 | `~/.local/bin/` (no sudo) |
| Teensy core | `teensy:avr` 1.62.0 | `~/.arduino15/` |
| udev rules | PJRC `00-teensy.rules` | `/etc/udev/rules.d/` (needed sudo) |

Index added: `https://www.pjrc.com/teensy/package_teensy_index.json`

## Firmware design notes

`teensy_bringup.ino` touches **only the onboard LED**. Until the section-B bench measurements are done, driving any pin risks 5 V into a part that clamps at 3.6 V.

Line protocol, newline-terminated, every reply tagged so a parser never guesses: `PING`/`INFO`/`HEALTH`/`ECHO`/`HELP`, plus an unsolicited `HEARTBEAT` every 1000 ms so a *silent* link is distinguishable from a *wedged* one without polling.

Two deliberate choices:

- **No `while (!Serial)`.** Every legacy Nano sketch has it. On a headless robot it blocks forever if the host never opens the port — the firmware would hang before it could report anything.
- **`restart` reports `SRC_SRSR`.** A board that silently reboots under motor load looks *identical* to a healthy one over USB, because CDC re-enumerates fast enough to miss. The i.MX RT1062's latched reset-cause register is the only way to tell. This will matter once motors draw current.

## Bugs found in my own tooling

| File | Bug | Fix |
|---|---|---|
| `health_check.py` | `close()` used `try/finally` with no `except`; a failed termios restore threw and **masked the entire report** | catch `termios.error`/`OSError`; a vanishing CDC port is not a health failure |
| `Makefile` | picked the upload port from `/dev/ttyACM*`, which cannot exist in RawHID | take it from `arduino-cli board list` (`teensy` protocol) |
| `Makefile` | `--input-dir build` relative — loader resolved it against its own cwd | absolute `$(CURDIR)/build` |
| `Makefile` | `-file=teensy_bringup` — arduino-cli emits `teensy_bringup.ino.hex` | derive `SKETCH` from `wildcard *.ino`, giving `teensy_bringup.ino` |

## Takeaways

1. **`16c0:0486` vs `16c0:0483` is the whole diagnosis.** The product ID names the USB type; no serial node can exist under RawHID regardless of drivers or permissions.
2. **Pin `usb=serial` in the FQBN.** Implicit defaults are how this recurs silently.
3. **The upload address is not the tty.** arduino-cli's `teensy` discovery protocol works even with no serial node — which is exactly the situation you're trying to escape.
4. **`teensy_post_compile` does not flash.** It messages a GTK app that must already be running. On headless hardware, find a display or use `teensy_loader_cli`.
5. **`~` becomes `/root` under sudo.** Use absolute paths in `sudo cp`.
6. **`/dev/ttyACM<N>` is not stable.** Observed moving 0→1→0 with nothing unplugged. Always use `/dev/serial/by-id/`.
7. **`dialout` does not cover `hidraw`.** Different subsystem, different rules.

## Follow-ups

| Action | Why |
|---|---|
| Replace the GUI loader with `teensy_loader_cli` | A background GTK app on `:0` is a fragile dependency — it dies with the desktop session. Needs `libusb-dev` and sudo |
| Use the by-id path in every ROS launch file | Prevents the port-numbering bug reaching production |
| Recheck temperature once enclosed | 54 °C idle in open air; airflow will be worse inside |
| Decide the ROS 2 transport | micro-ROS on `SerialUSB1` with `Serial` kept as console — see ACTION-PLAN |

## Related

- [001](001-2026-08-04-jetson-wifi-unreachable.md) — the `192.168.55.1` USB link all of this work was done over
- [002](002-2026-08-04-usb-topology-and-peripheral-split.md) — why the lidar is *not* on this Teensy
- [`../ACTION-PLAN.md`](../ACTION-PLAN.md) section C
