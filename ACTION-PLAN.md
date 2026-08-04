# Gerdoo — Action Plan

**Created:** 2026-08-04 (Tue) · **Horizon:** 2026-09-01 · **Goal:** Arduino Nano → Teensy 4.1 migration, powered and driving under ROS 2 Humble on the Jetson.

Wiring truth lives in [`inventory.md`](inventory.md). Problem write-ups live in [`logs/`](logs/README.md). `PINOUT.md` is the **legacy Nano build and is stale** — do not wire from it.

Every task has a pass condition with a number in it. If you cannot measure it, it is not done.

---

## Sequencing

Three hard gates. Nothing downstream of a gate starts until it clears.

```
A  Infrastructure ──┐
                    ├─> C  Teensy serial ──> D  Wiring ──> E  Drive
B  Bench measure  ──┘         │
                              └─> F  ROS 2 interface   (parallel — no wiring needed)
```

- **B blocks D** — never wire an unmeasured rail into a 3.3V part.
- **C blocks D** — no serial port means no way to see what the firmware is doing.
- **B1 blocks the charger** — if the XL4015 is CV-only, that plan dies and gets replaced.
- **F runs in parallel.** The ROS interface needs only a working serial link, not wired peripherals — which is why it is already done while B and D are still open.

---

## A — Infrastructure

| # | Task | Target | Pass condition |
|---|---|---|---|
| **A1** | ~~Disable wifi power save~~ | ~~2026-08-04~~ | ✅ **Done 2026-08-04.** `iw dev wlP1p1s0 get power_save` → `off`. See [log 001](logs/001-2026-08-04-jetson-wifi-unreachable.md) |
| **A2** | **Confirm the fix survives idle** | **2026-08-04** | Leave Jetson untouched **≥ 2 h**, then cold `ssh user@<robot-ip>`. Connect in **< 5 s**, first try. Power save only bites after idle — A1 is unproven until this passes |
| **A3** | Move wifi to 5 GHz | 2026-08-06 Thu | Currently ch 1 / 2412 MHz, jitter stddev **22.6 ms** against a **5.3 ms** floor. After: stddev **< 10 ms** over 50 pings |
| **A4** | DHCP reservation for `<jetson-wifi-mac>` | 2026-08-06 Thu | Fritz!Box pins `.173`. Reboot Jetson, IP unchanged |
| **A5** | ~~Document the USB fallback in `inventory.md`~~ | ~~2026-08-06~~ | ✅ **DONE 2026-08-04.** New **🔑 Access** section at the top of `inventory.md`: both paths, the power-save warning, stable by-id device paths, and the running services |
| **A6** | ⚠️ **Replace the test control-panel password** | **now** | A throwaway password (value deliberately not recorded here) was set during [log 008](logs/008-2026-08-04-control-panel-camera-lidar.md) testing and is **live on the LAN right now**. It gates a camera stream. Fix: `cd ~/robot-face && python3 manage.py set-password && systemctl --user restart robot-face`, then confirm the old one is rejected |

> The camera and lidar endpoints refuse to work unless a password **exists** (403 `password_required`), verified against an auto-authenticated session — so the panel cannot expose a video feed unprotected. But the password currently in place was chosen during testing, not by you.

> **A2 is the only one of these that gates anything.** If it fails, power save is not the whole story and A3/A4 wait.

---

## B — Bench measurements

**Meter only. Nothing connected to the Teensy.** These are the six open items from `inventory.md`.

| # | Measure | Target | Pass condition | If it fails |
|---|---|---|---|---|
| **B1** | **XL4015 pot count** | 2026-08-05 Wed | Count trimpots. **2 = CC/CV**, charger plan proceeds. **1 = CV only** | ⚠️ **Do not charge lithium with a CV-only converter.** Buy a real 3S CC/CV charger |
| **B2** | **MINI560 on 12V** | 2026-08-05 Wed | 12V in, output **bare**, meter across OUT±. Want **5.00 V ±0.15 V**. Settles the old servo-board failure | If dead, use the spare. If it reads 5V, root cause was the **7 V input floor** — it was fed from Nano 5V |
| **B3** | **Encoder wire colors** | 2026-08-05 Wed | Identify encoder VCC vs motor lead on the actual 36GP-555. Common: **blue = encoder VCC, red = motor** | ⚠️ Legacy notes say red. Wrong guess puts **12 V into a 3.3 V** encoder supply. Verify against motor body, not notes |
| **B4** | **HC-SR04 revision** | 2026-08-05 Wed | Power at 5V, measure **ECHO idle-high**. **5.0 V** = classic, needs divider. **3.3 V** = V2.0, direct | Classic → use HC-SR04P at 3.3V instead, or fit the divider |
| ~~**B5**~~ | ~~RPLIDAR C1 TX level~~ | — | ❌ **DELETED 2026-08-04** — lidar goes to Jetson USB, never touches the Teensy. See [log 002](logs/002-2026-08-04-usb-topology-and-peripheral-split.md) | — |
| **B6** | **COB LED strip voltage** | 2026-08-07 Fri | 5V → dirty rail. 12V → battery rail via LR7843 MOSFET | Determines which rail it lands on |
| **B7** | **Screen power draw** | on arrival | Meter the panel's **own** supply. Prior session measured **~5.9 W total Jetson board power** running the face (2D 5.79 W / WebGL 5.85 W) and concluded it is *display-dominated* — but that is board power, and the panel is fed separately, so it likely sits **outside** that figure | Settled already: **do not tune the renderer for battery** — screen-on is the cost, renderer choice is noise (~0.06 W between them). 60→30 fps was worth ~0.5 W. See [log 006](logs/006-2026-08-04-robot-face-adoption.md) |
| **B8** | **Camera enumeration** | on arrival | Set `uvcvideo quirks=128` **first**, then plug both OV9281s in and check `dmesg` for `Not enough bandwidth` | If the second refuses, step one to 640×400 — only effective *with* the quirk set |

**Teensy 4.1 is not 5V tolerant. ESD clamp is 3.6 V.** Every pin that reaches it must measure ≤ 3.6 V *before* it is connected.

---

## C — Teensy serial mode ✅ COMPLETE 2026-08-04

Was `16c0:0486` (RawHID) with no `/dev/ttyACM*`. Now `16c0:0483` (Serial), healthy, 12/12 checks pass. Full write-up: [log 003](logs/003-2026-08-04-teensy-rawhid-bringup.md).

| # | Task | Result |
|---|---|---|
| **C1** | Toolchain on Jetson | ✅ arduino-cli 1.5.2-rc.1 in `~/.local/bin` (no sudo), Teensy core `teensy:avr` 1.62.0, PJRC udev rules installed. Builds natively — PJRC ships `aarch64-linux-gnu` |
| **C2** | Firmware source | ✅ Wrote `teensy_bringup/` fresh — legacy Nano sketches are not portable |
| **C3** | Rebuild as Serial | ✅ `usb=serial` **pinned in the FQBN**, not left to a default |
| **C4** | Verify the port | ✅ `16c0:0483`, `/dev/ttyACM*` `root:dialout 660`, `jarvis` already in `dialout` |
| **C5** | Round-trip test | ✅ 64-byte ECHO byte-exact, **0.2 ms** RTT |
| **C6** | Write the log | ✅ [log 003](logs/003-2026-08-04-teensy-rawhid-bringup.md) |

Measured: RTT **0.2 ms** · loop **7.06 MHz** · restart **`power_on`** · heartbeat **1.000 s** min *and* max · **54.0 °C** idle · FLASH 13,100 B, RAM1 486 KB free.

### Three findings that constrain later work

1. **`/dev/ttyACM<N>` is not stable.** Observed moving 0→1→0 with nothing unplugged, purely from re-enumeration on flash. **Never hardcode it** — in the Makefile, in ROS launch files, anywhere. Use:
   ```
   /dev/serial/by-id/usb-Teensyduino_USB_Serial_19627940-if00
   ```
   Keyed on the board's own serial number, so it also disambiguates boards once the arm Teensy is added.

2. **No PROGRAM button needed, ever.** With udev rules installed, `teensy_reboot` soft-reboots over HID. Flashing needs no physical access to the robot.

3. **Flashing depends on a GTK app on `DISPLAY=:0`.** `teensy_post_compile` does not flash; it messages the Teensy Loader application. Works today because the Jetson has a live session — but it dies with the desktop. See **C7**.

| # | Task | Target | Pass condition |
|---|---|---|---|
| **C7** | ~~Replace GUI loader with `teensy_loader_cli`~~ | ~~2026-08-08~~ | ✅ **DONE 2026-08-04.** Flashed with `DISPLAY`/`XAUTHORITY` unset; 12/12 checks pass after. GUI loader killed permanently. [Log 005](logs/005-2026-08-04-headless-teensy-flashing.md) |

> ⚠️ `teensy_loader_cli` is **built from source, not apt-managed** — clone at `~/src/teensy_loader_cli`. After any OS reflash: `make && install -m 0755 teensy_loader_cli ~/.local/bin/`.

---

## D — Power and wiring

**Blocked by B and C.** Build the power tree first, verify each rail unloaded, then add loads one at a time.

| # | Task | Target | Pass condition |
|---|---|---|---|
| **D1** | Star ground | 2026-08-08 Sat | One common point. **< 50 mV** between any two ground points under load |
| ~~**D2**~~ | ~~MINI560 #1 → lidar (quiet rail)~~ | — | ❌ **DELETED 2026-08-04** — lidar powers off Jetson USB. MINI560 #1 is now a **spare**, and the 150 mV ripple constraint is gone with it |
| **D3** | MINI560 #2 → servos, PCA9685 V+ (dirty rail) | 2026-08-08 Sat | 5.0 V under servo load. Input **≥ 7 V** — feed from **12 V battery**, never from a 5V rail |
| **D4** | Cut Teensy VUSB↔VIN pad | 2026-08-08 Sat | Trace cut before any external 5V reaches the Teensy. Prevents backfeeding the Jetson USB |
| **D5** | **IBT-2 pin 7 (VCC) → Teensy 3.3 V** | 2026-08-10 Mon | ⚠️ **Not 5 V.** The 74HC244 needs **3.5 V** V_IH at 5 V VCC (0.7 × VCC) and the Teensy only puts out 3.3 V. At 3.3 V VCC the threshold drops to **2.31 V** and it works. Same for R_EN/L_EN |
| **D6** | Encoders → Teensy 3.3 V | 2026-08-10 Mon | Powered at **3.3 V** so output level follows supply. Uses B3's result |
| **D7** | Ultrasonic per B4 | 2026-08-10 Mon | HC-SR04P at 3.3 V direct. Classic HC-SR04 needs a divider on ECHO |
| **D8** | ~~Lidar → Jetson USB port~~ | ~~2026-08-11~~ | ✅ **DONE 2026-08-04, 7 days early.** Publishing `/scan` at **10.008 Hz**, std dev 0.001 s, 4.5 % of one core, health `OK`. Zero firmware written. [Log 004](logs/004-2026-08-04-rplidar-c1-bringup.md) |
| **D9** | Rail audit before power-on | 2026-08-11 Tue | **Every** Teensy-facing pin measures **≤ 3.6 V**. Written down, not remembered |

**No level shifters anywhere in the robot** — everything that talks to the Teensy is powered at 3.3 V so its output level follows.

---

## E — Bring-up

| # | Task | Target | Pass condition |
|---|---|---|---|
| **E1** | Motor PWM at **20 kHz** | 2026-08-14 Fri | `analogWriteFrequency(RPWM_PIN, 20000)`, `analogWriteResolution(12)`. **Legacy Nano ran ~31.4 kHz — over the BTS7960 25 kHz limit** |
| **E2** | Encoder counts | 2026-08-14 Fri | Both wheels count, correct sign both directions. Hardware quadrature decoder, not interrupts |
| **E3** | Lidar stream | 2026-08-15 Sat | Full scans at 460800 8n1, **zero** dropped frames over 60 s |
| **E4** | ROS 2 bridge | 2026-08-18 Tue | Teensy ↔ Humble over `/dev/ttyACM0`. Odom + scan topics publishing |
| **E5** | First drive | 2026-08-21 Fri | Closed-loop drive, both motors, no brownout, no lidar dropout under motor load |

---

## F — ROS 2 interface ✅ FIRST NODE UP 2026-08-04

`/teensy_node` in the ROS graph. Pub, sub, and unattended reconnect all verified. [Log 007](logs/007-2026-08-04-microros-bringup.md).

| # | Task | Result |
|---|---|---|
| **F1** | micro-ROS toolchain | ✅ `micro_ros_arduino` 2.0.8-humble + agent built from source. `vcstool` via `pip3 --user` |
| **F2** | **Dual Serial** (`usb=serial2`) | ✅ `if00` console / `if02` micro-ROS. Console proven working **while the agent is down** |
| **F3** | Transport on `SerialUSB1` | ✅ Weak-symbol override in the sketch — **no library edits**, survives upgrades |
| **F4** | Pub / sub | ✅ `/teensy/heartbeat` 1.000 Hz (σ 0.6 ms), `/teensy/temperature` 1.001 Hz, `/teensy/led` actuates |
| **F5** | Reconnect state machine | ✅ Agent killed → detected → **recovered in 8 s unattended**, `connects=2 drops=1` |

| **F6** | ~~systemd user unit for the agent~~ | ✅ **DONE 2026-08-04, 4 days early.** `micro-ros-agent.service` enabled. `kill -9` → systemd restarts (`NRestarts=1`) → firmware reconnects (`connects=4 drops=3`) → heartbeat back at 1.000 Hz, **unattended** |

**Two independent recovery layers** — systemd restarts the agent; the Teensy state machine reconnects to it. Either alone leaves a hole.

| # | Task | Target | Pass condition |
|---|---|---|---|
| **F6b** | **Confirm the unit survives a real reboot** | next Jetson reboot | Currently *inferred* from `enabled` + the `robot-face` precedent, **not observed**. Depends on gdm autologin starting the `jarvis` session. After reboot: `systemctl --user is-active micro-ros-agent` → `active`, and `/teensy/heartbeat` at 1 Hz with nothing launched by hand |
| **F7** | Custom messages | 2026-08-14 Fri | `Int32`/`Float32` cannot carry encoder ticks, battery volts, motor state |
| **F8** | Decide the `ros2_control` boundary | 2026-08-14 Fri | micro-ROS suits lights/weather/servo goals; the drive loop likely wants a `hardware_interface` over its own protocol |

> ⚠️ **`platform.txt` is patched in `~/.arduino15`** to link precompiled libs. **Any Teensy core reinstall or update silently reverts it** — symptom is a wall of `undefined reference` at link. Backup: `platform.txt.orig`.

**Memory cost:** FLASH 13 KB → **264 KB** (7.78 MB free), RAM1 312 KB free, loop 7.06 → 4.36 MHz.

## Charging — conditional on B1

Only if the XL4015 has **two** pots.

| Setting | Value |
|---|---|
| CV | **12.60 V** (3S × 4.20 V) |
| CC | **~2 A** |
| Input | 19 V |

**Set both before connecting the battery**, output bare, meter on the terminals. Fit a **series Schottky** for reverse blocking — the 10A10 rectifiers on hand are the wrong part for this.

> ⚠️ **The BMS is a safety net, not a charge controller.** It protects against a fault; it does not regulate a charge curve. A converter set wrong will be allowed to do damage right up until the BMS cuts, and by then cells have already been overcharged.

---

## Milestones

| Date | Milestone | Gate |
|---|---|---|
| ~~2026-08-07~~ **2026-08-04** | ~~Teensy on `/dev/ttyACM0`~~ **Teensy healthy on Serial, 12/12 checks** | ✅ **C4 — done 3 days early** |
| **2026-08-04** | **Lidar publishing `/scan` at 10 Hz** | ✅ **D8 — done 7 days early** |
| **2026-08-04** | **`/teensy_node` in the ROS graph, agent auto-restarting** | ✅ **F1–F6 — done 4 days early** |
| 2026-08-05 Wed | Bench measurements done | B1–B4 |
| 2026-08-11 Tue | Power tree verified, every pin ≤ 3.6 V | D9 |
| 2026-08-15 Sat | Sensors streaming | E3 |
| 2026-08-21 Fri | First closed-loop drive | E5 |

## Standing rules

1. **Measure before connecting.** Teensy 4.1 clamps at 3.6 V and does not survive 5 V.
2. **One load at a time.** Add, verify the rail, then add the next.
3. **Keep the USB fallback wired.** `192.168.55.1` works when wifi does not.
4. **Log every problem** in `logs/` — including the wrong turns.
5. **`inventory.md` is the wiring reference.** `PINOUT.md` is the old Nano build.
6. **Never hardcode `/dev/ttyACM<N>` or `/dev/ttyUSB<N>`.** Both move. Use the by-id paths:
   ```
   teensy: /dev/serial/by-id/usb-Teensyduino_USB_Serial_19627940-if00
   lidar:  /dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_ec8fc9bc95d5ef11afac704b49d2c684-if00-port0
   ```
7. **MCU for determinism, not for load.** Settles every "which side does this go on?" question — see [log 002](logs/002-2026-08-04-usb-topology-and-peripheral-split.md).
8. **Check what is already installed before writing code.** `rplidar_ros` saved ~2 weeks of firmware work (log 004).
9. **Scope `set +u` around any `source` of a ROS setup script.** They are not `set -u` clean — `setup.bash` dies on `AMENT_TRACE_SETUP_FILES` (log 007).
10. **In service units, exec the real binary, not `ros2 run`.** The wrapper orphans the process, which then holds the serial device (log 007).
11. **`pkill -f` / `pgrep -f` over SSH can match the shell running them** and kill your own connection or return bogus counts. Resolve the PID first, then `kill` it. Hit four times in one session.
12. **Process death is not a stop signal.** Anything holding physical state — motor, heater, valve, laser — needs an explicit shutdown command *and* a backstop for when the graceful path fails. ROS units need `KillSignal=SIGINT` (log 009).
