# 012 — COB LED strip with ambient-light brightness control

| | |
|---|---|
| **Date** | 2026-08-23 → 2026-08-26 |
| **Type** | Feature bring-up — lighting + sensor |
| **Status** | ✅ Working — strip on its own rail, ambient tracking live |
| **Severity** | Routine |

---

## Goal

Drive the COB LED strip from the 5V servo rail, dimmed by PWM, with brightness
following a photoresistor so the strip brightens as the room darkens.

## What was actually built

The original request was "5V → potentiometer → LED strip". That does not work: a
potentiometer in series with the strip is a rheostat carrying the full load current,
and a 1/4W pot near 0Ω is a short across the rail that also feeds the servos.

Correct split, which is what got built:

- **MOSFET** does the dimming, via PWM from Teensy pin 4
- **Photoresistor** on A1 is the input
- A potentiometer, if added later, is a **knob the ADC reads** — never in the load path

## Final wiring

Strip voltage was an open item (`inventory.md` open item 2). **Answered: it is a 5V
strip** — full brightness on the 5V rail with the MOSFET bypassed.

See `PINOUT.md` for the terminal-by-terminal tables.

## The evening that got lost, and why

The first MOSFET module (LR7843, `inventory.md` line 1078) never switched. Symptoms:

- Rail live at 5V ✓
- Shorting `LOAD` to `−` lit the strip at full ✓ — so the power path was fine
- Teensy pin 4 swung 0 ↔ 3.3V when disconnected ✓
- Pin 4 collapsed to 0V when connected to the module's `PWM` header
- Neither signal-wire orientation drove the gate
- **Jumpering the header `PWM` straight to 5V also did nothing** — which ruled out the
  "3.3V under-drives an opto input" theory

Replaced with a **D4184 dual-MOSFET module** (logic-level, "trigger source DC3.3V–20V"
stated as a spec). Worked immediately on the first bench test.

### Lesson

**Bench-test a switching module before it goes on the robot.** 5V in, a single LED and
a 220Ω resistor as the load, signal from the microcontroller. Two minutes, and it
catches a bad or wrong-spec board before it is buried in the loom.

### Parts warning

The ubiquitous red **"MOS Module" (HW-517) is IRF520-based** and its listings claim
3.3V compatibility. Vgs(th) runs to 4V and Rds(on) is specified at a 10V gate, so a
3.3V pin leaves it in the linear region — dim output, hot FET, or nothing. Listings for
it often show a 3.3V board next to it anyway. Check the TO-220 marking in the photos,
not the bullet points.

Use a logic-level part: **D4184/AOD4184**, **IRLZ44N**, or **IRLB8721**.

## Flashing — two blockers worth remembering

Both cost time and will recur on every future Teensy flash.

**1. `teensy_loader_cli -s` cannot work with `usb=serial2`.** The soft reboot is sent
over HID, and Dual Serial (PID `048b`) exposes two CDC interfaces and **no HID
interface**. It fails with `Error opening USB device: No error` and then waits forever
for a button press.

Fix: opening the primary CDC port at **134 baud** is the Teensy core's own bootloader
trigger and needs no HID. `B134` is a standard POSIX baud, so plain `stty` does it — no
pyserial, which is not installed system-wide on the Jetson.

```sh
stty -F /dev/serial/by-id/usb-Teensyduino_Dual_Serial_19627940-if00 134
sleep 2
lsusb | grep 16c0:0478          # HalfKay bootloader has appeared
teensy_loader_cli --mcu=TEENSY41 -w -v build/sketch.ino.hex
```

**2. `micro-ros-agent.service` holds `if02` open** and blocks the reboot. It must be
stopped before flashing and started again afterwards.

Both are now handled inside the `upload` target of `teensy_microros/Makefile`. This
supersedes the note in `logs/005` about arduino-cli delegating to `teensy_post_compile`
— that is still true, but `-s` was never a working substitute on this USB mode.

## Firmware — `microros-0.4.0`

| Interface | Type | Notes |
|---|---|---|
| `/teensy/light_level` | `std_msgs/Float32` pub, 1 Hz | 0 = dark room, 1 = bright |
| `/teensy/led_strip` | `std_msgs/Float32` sub | 0–1 forces a level; **negative returns to auto** |
| `LIGHT` | console | raw, normalised, calibration points, duty, mode |
| `CAL dark` / `CAL bright` | console | store the current reading as that endpoint |
| `STRIP auto` / `STRIP 0-100` | console | follow the sensor, or force a level |

Design notes:

- **18 kHz PWM.** Inside the D4184's 0–20 kHz spec, above adult hearing, and far above
  any camera shutter so it cannot band the OV9281s or the Brio.
- **20 Hz update, 0.05 smoothing** ≈ a one-second time constant. Deliberate: the strip
  illuminates its own sensor, and a fast loop would oscillate. Mount the sensor facing
  away from the strip as well.
- **Gamma 2.0** on the duty cycle. Perceived brightness tracks roughly the square of
  duty, so a linear ramp looks wrong at the bottom end.
- `analogWriteResolution(12)` is global to `analogWrite`, but the Servo library does
  not use it — the neck servos are unaffected.

## The strip browns out the servo rail

Reported symptom: closing a hand over the light sensor put "pressure on the neck
motors" — the servos straining, not tracking smoothly.

First diagnosis was wrong. `gesture.service` runs a MediaPipe hand tracker that
commands the neck, so a hand entering frame *does* move it — but tracking moves the
neck smoothly, it does not strain it. Straining is a power symptom.

**Confirmed by forcing the strip to full with no hand near the camera:**

| Strip duty | Pack voltage |
|---|---|
| 0 | **11.13 V** |
| 4095 (full) | **10.94 V** |

Repeatable ~150–250 mV sag at the pack, caused by the strip alone. A brightness sweep
was also run, but its intermediate points are noisy — the Jetson and servos move the
pack voltage too, so the curve's shape cannot be cleanly attributed. The 0-vs-full
comparison is the reliable measurement.

Cause: the strip is on the **same LM2596S 5V rail as the SG90 neck servos**. This is
exactly the "5V dirty rail" grouping the architecture section already warned about —
SG90 servos and the COB strip sharing one converter.

### Fix — the strip needs its own rail

Use one of the **6 spare MINI560** modules (JW5069A, 7–20V in, 5V fixed out, 5A), fed
from the **12.6V power pack**.

⚠️ Feed it from 12.6V, **never from the existing 5V rail**. The MINI560's input minimum
is 7V and it needs ≥2V of input-to-output headroom. Feeding one from 5V is the most
likely cause of the earlier dead-MINI560 incident (`inventory.md` line 393).

### Interim mitigation, in firmware

`STRIP_DUTY_MAX = 1600` (~39% duty) was added to cap brightness so the sag stayed small.
One SG90 has already been lost to abuse (`servo-problem.md`), so the ceiling stayed low
until the dedicated rail existed.

### ✅ Resolved — MINI560 fitted 2026-08-26

The strip now has its own **MINI560** (JW5069A, 5V fixed, 5A) fed from the **12.6V power
pack**, independent of the LM2596S servo rail. Confirmed working. The neck servos no
longer strain when the strip brightens.

`STRIP_DUTY_MAX` was raised back to `STRIP_MAX` on 2026-08-26. Verified at full duty
(4095/4095) on the dedicated rail: pack steady at ~10.93 V, loop rate 999 Hz, agent
connected, no servo strain.

## Follow-on: servo rail to 6V

Separate from this work, but it came out of it. The plan is to raise the LM2596S servo
rail from 5V to 6V for more SG90 torque. **Not yet done.** Three checks must pass first,
recorded as B10 in the action plan and open item 12 in the inventory:

1. Nothing else on that rail — anything rated 5V absolute is damaged at 6V
2. ⚠️ **Teensy `VIN` must not be fed from it. VIN maximum is 5.5V** — 6V destroys the board
3. Set the pot with the load disconnected, meter on the bare output, then reconnect

⚠️ These SG90s are recorded at **4.8–5V**, not the 4.8–6V of generic datasheets. 6V is at
or past their rating: more torque, but more heat and faster wear on plastic gears already
carrying a 5.5" screen. One tilt servo is already dead from stalling — raising the voltage
gives a marginal drivetrain more force to hurt itself with, rather than fixing the overload.

**The better fix uses parts already owned:** two of the **16× STS3215** bus servos. 25×
the torque, metal gears, position feedback, and they run straight off the 12V pack — which
deletes the 5V servo rail question entirely. The migration notes already call for this.

## Calibration — measured 2026-08-26

| Condition | Raw ADC on A1 |
|---|---|
| Covered by a hand | **529** |
| Normally lit room at night | ~950–1270 |
| Full daylight | **3163** |

Baked into the firmware as `ldrRawDark = 529` / `ldrRawBright = 1400`. **The bright
endpoint is deliberately not the 3163 daylight figure.** Against that ceiling a lit
evening room maps to ~78% brightness and the strip would run near-full every night.
1400 means "the room is adequately lit, strip off", and anything brighter clamps.

Console `CAL` values live in RAM only — they do not survive a reboot **or a reflash**,
which caught us once mid-session. Hardcoding is the persistent path.

Verified end to end: sensor covered → `norm=0.000` → strip driven to 4093/4095
automatically in auto mode. Uncovered → `norm=1.000` → strip 0.

## Open

- **Strip current never measured directly.** Everything about its draw is inferred from
  pack sag. A meter in series at full brightness sizes the fuse and confirms MINI560
  headroom.
- **No inline fuse fitted yet** on the strip's 5V branch. `inventory.md` calls fusing
  the biggest safety gap in the build; this branch is currently unprotected.
- **No star-ground bus bar.** Several dead ends during debugging traced back to
  uncertainty about what was grounded to what.
