# 011 — 19V charger → step-down → 12V battery charging test

| | |
|---|---|
| **Date** | 2026-08-19 |
| **Type** | Bench test — charger / step-down voltage management |
| **Status** | ⏳ In progress (session opened, updates appended as the test proceeds) |
| **Severity** | Safety-relevant — lithium charging |

---

## Goal

Test the connection from the 19V charger and manage the charging voltage for the 12V moving (power) battery pack via a step-down buck converter.

## Setup (per inventory.md — Charging section)

- **Source:** 19V DC charger (45W, included with the Jetson dev kit supply)
- **Converter:** XL4015 #1 (must be the **CC/CV variant** — two pots + red/blue/green LEDs)
- **Target pack:** 3S Li-ion (INR21700-40T power pack, or INR21700-50E electronics pack)

### Target charge settings

| Setting | Value | Why |
|---|---|---|
| CV | **12.60V** exactly | 4.20V/cell × 3S — full charge for Li-ion |
| CC | ~2A | below the 4A (40T) / 4.75A (50E) cell max; gentler, longer pack life |

### ⚠️ Safety guards from the inventory

1. **Verify the XL4015 is the CC/CV variant.** Single-pot = CV-only, no current limit → do NOT charge lithium with it.
2. **Set CV and CC with a meter, no pack connected**, then connect.
3. **The 3S BMS is a safety net, not a charge controller.** It cuts off on cell overvoltage; it does not regulate the charge profile. Passive balancing is slow.
4. **XL4015 has no reverse-current blocking.** A connected pack leaks backward when the 19V source is off. Add a Schottky in series, or a disconnect plug in the charge path.
5. **Do not leave early charge cycles unattended.** Confirm pack voltage plateaus at 12.6V and current tapers.

## Question answered at session start

**Q: What voltage for the 21700 cells in 3S2P?**

**A: 12.60V** — the same as any 3S Li-ion pack.

- The **2P** (parallel) part doubles capacity (mAh) and current capability (A) but does **not** change voltage. Parallel cells share one voltage.
- A 3S2P pack has the identical voltage range as a 3S1P pack:
  - Nominal: ~11.1V (3.7V/cell)
  - **Full charge: 12.60V (4.20V/cell)**
  - Discharge cutoff: ~9.0V (3.0V/cell), absolute floor 7.5V (2.5V/cell)
- Never exceed 12.60V — overcharging Li-ion is a fire risk.

> ⚠️ **Config discrepancy to resolve:** The inventory records both packs as **3S** with **4 cells purchased** of each type (3 in the pack + 1 spare) — i.e. **3S1P**, not 3S2P. A 3S2P pack needs **6 cells** of the same type. Either more cells exist than are recorded, or the pack is 3S1P. Confirm the actual cell count before charging.

## Progress

### 2026-08-19 — Session opened
- Starting the bench test: 19V charger → XL4015 step-down → 3S pack.
- More details to be appended as the test proceeds.

### 2026-08-19 — Pack wouldn't charge past 11.69V — cell imbalance

**Symptom:** Pack reported as "fully charged" but terminal voltage sat at **11.69V** (3.90V/cell ≈ 70% SoC), not the expected 12.60V.

**Diagnosis steps:**
- XL4015 output measured **open-circuit (no pack): 12.68V** → CV setting correct (slightly high — 4.227V/cell; trim to 12.60V).
- When pack connected, voltage dropped to 11.69V → the converter wasn't the problem.
- **Root cause: cell imbalance.** One cell had reached the BMS overvoltage cutoff (~4.25V) while the other two were still at ~3.7V. The BMS disconnected the pack, charging stopped, and the *average* read 11.69V — even though one cell was actually full.

**Fix (interim):** Shuffled the cells between positions. Current is now flowing and charging resumes.

**Verification (pending):** Confirm pack voltage rises to 12.6V and current tapers to ~0A. Report to follow.

### 2026-08-19 — CC set to 2.37A; XL4015 LED went off (BMS cut off again)

- CC adjusted to **2.37A** — appropriate, well within cell specs and XL4015/45W supply limits. Not the cause of the imbalance.
- Charging LED on the XL4015 went from ON → OFF after the shuffle. Current stopped — BMS cut off again due to the same cell imbalance.
- **Resting voltage vs charging voltage clarified:** unplugged = 11.7V (real pack state), plugged in = 12.7V (converter output). Normal CC/CV behaviour — the 12.7V is the charging voltage, not the SoC.
- CV trimmed discussion: 12.68V open-circuit = 4.227V/cell, slightly above 4.20V spec. Trim to 12.60V.

### 2026-08-19 — Datasheet confirmed: 3.6V is nominal, 4.2V is charge target

**Confusion:** User found "3.6V" listed as cell voltage on the product page and thought the charge target might be wrong.

**Samsung SDI official datasheet (INR21700-40T) confirms:**
- Nominal voltage: **3.6V** (§3.3) — the nameplate/average discharge voltage, NOT a charge target
- Standard charge: **CCCV, 2A, 4.20V**, 200mA cut-off (§3.4 / §7.1) — this is what you charge TO
- Rated charge: CCCV, 6A, 4.20V, 100mA cut-off (§3.5)
- Discharge cut-off: 2.5V (§3.8)
- Ex-factory voltage: 3.34–3.49V (§7.12)
- Chemistry: Li-ion NCA (LiNiCoAlO₂)
- Internal impedance: ≤ 12mΩ (§7.5)
- Datasheet pack design guideline §2.6.2: *"The system should be equipped with a device to monitor each voltage of cell block to avoid cell imbalance"* — confirms the BMS-only approach is insufficient.

**Conclusion:** 12.60V for 3S (4.20V/cell) is the correct charge target. Nothing was wrong with the voltage setting. Cells measured at 3.6V are at ~20-30% SoC and need charging.

**Root cause of charging failure:** severe cell imbalance — during charging, one cell races to 4.2V (BMS cutoff) while others lag at ~3.6V. 0.6V gap is massive. Possible causes: low-capacity cell, high-IR cell, or poor contact on one cell in the holder.

**Action items:**
1. Charge each cell individually to 4.2V (set XL4015 to 4.2V, one cell at a time) to equalise the starting point
2. Or acquire a proper 3S balance charger
3. Check cell holder contacts for poor connections
4. Trim XL4015 CV from 12.68V to exactly 12.60V

### 2026-08-19 — Reverse-current protection diode ordered

- **Problem identified:** XL4015 has no reverse-current blocking. When the 19V source is off and the pack stays connected, the battery slowly drains backward through the converter. Not dangerous (slow drain), but wastes charge.
- **Why the 10A10 (already in inventory) was rejected:** Silicon diode, ~0.7-1.0V forward drop that varies with current. This was likely the cause of the earlier 11.69V pack voltage (converter at 12.68V minus ~1V diode drop = ~11.7V). The varying drop makes it impossible to set a stable CV for Li-ion charging.
- **Solution ordered:** 20× 30SQ050 Schottky diode (30A, 50V) from Amazon.de — €5.99, ASIN B0BYVGWTHD. Schottky drop is only ~0.3V and nearly constant across the charge cycle.
- **Installation plan (when diodes arrive):**
  - Solder inline on the positive wire between XL4015 output and pack
  - Orientation: anode (no band) → converter side, cathode (band/`-`) → pack side
  - Current flows converter → battery (charging), blocked from flowing battery → converter
  - **Set CV to 12.60V measured at the pack terminals (after the diode)** — the diode eats ~0.3V so the converter output will be ~12.9V
- **Until diodes arrive:** keep using the manual disconnect (unplugging). Works fine for bench testing.
- **Inventory updated:** Added 30SQ050 entry to inventory.md with specs and installation notes.


### 2026-08-19 — Main battery voltage monitoring on Teensy (step 1 of panel integration)

**Goal:** Read main battery (3S2P) voltage via Teensy A0, publish via micro-ROS, display on robot-face control panel.

**Hardware wired:**
- Voltage Sensor Module Max 25V (5:1 divider)
  - Screw terminals: VCC → battery +, GND → battery -
  - 3-pin header: S → Teensy A0 (pin 14), + → Teensy 3.3V, - → Teensy GND
- Module confirmed outputting 2.52V on S pin (multimeter), 12.6V battery

**Firmware modified:** `teensy_microros.ino` v0.2.0
- Added `analogReadResolution(12)` + `analogReadAveraging(8)` in setup()
- New publisher: `/teensy/battery_main` (std_msgs/Float32) at 1 Hz
- New console command: `BATTERY` (shows voltage, raw ADC, pin voltage)
- Battery voltage included in heartbeat line: `bat_v=12.61`

**Bug found and fixed: Teensy ADC resolution mismatch**
- **Symptom:** ADC read 0.63V on A0, but multimeter read 2.5V on the same pin
- **Root cause:** Teensy 4.1 defaults to 10-bit `analogRead()` (0–1023), but firmware calculated with `ADC_MAX=4095` (12-bit). Raw value 782 was interpreted as 782/4095×3.3=0.63V instead of 782/1023×3.3=2.52V.
- **Fix:** `analogReadResolution(12)` in setup() — one line, brings the ADC to full 12-bit range matching the calculation.
- **Lesson:** The Teensy 4.1 has 12-bit ADC hardware but defaults to 10-bit for Arduino compatibility. Always set `analogReadResolution(12)` explicitly.

**Debugging path (for the record):**
1. Initial reading 3.15V instead of ~12.5V — suspected floating pin / missing ground
2. Added ground wire — no change
3. Scanned all 18 analog pins — none read 2.49V (A0 read 0.63V, others near 0)
4. Repeated reads with delay — stable at 0.63V, no climbing (ruled out impedance)
5. Disconnected S wire — A0 dropped to 0.22V (confirmed S is on A0)
6. Multimeter read 2.5V on S while connected to A0 — module works, ADC is wrong
7. Realised raw=782 ÷ 1023 × 3.3 = 2.52V — the ADC was 10-bit, not 12-bit
8. Added `analogReadResolution(12)` — reading jumped to 12.61V ✅

**Verified end-to-end:**
- Console: `BATTERY main_v=12.608 raw=3129 pin_v=2.522` ✅
- ROS 2: `ros2 topic echo /teensy/battery_main` → `data: 12.61` ✅
- Heartbeat: `bat_v=12.61` ✅

**Files updated:**
- `teensy_microros/teensy_microros.ino` — firmware v0.2.0
- `PINOUT.md` — rebuilt from scratch for Teensy 4.1, A0 wiring documented
- `inventory.md` — 30SQ050 Schottky diode added (earlier in session)

### 2026-08-20 — XL4015 destroyed by reverse polarity

**Incident:** While repurposing an XL4015 to step down the 12.6V battery to 5V for motors, the battery + and - were accidentally reversed on the XL4015 input. The module smoked immediately. Disconnected within seconds.

**Root cause:** XL4015 has no reverse polarity protection. Reversed input sends full battery current (35A+ available from 3S2P pack) through the input capacitor and freewheeling diode with no resistance. The input electrolytic capacitor (polarized) vents and the diode shorts.

**Damage:** XL4015 almost certainly destroyed. Battery pack confirmed OK at 12.5V — disconnected fast enough, BMS not triggered.

**Lesson:** Always verify polarity with a multimeter before connecting any buck converter to a high-current source. The XL4015, MINI560, and LM2596S all lack reverse polarity protection.

**Resolution:** LM2596S (with built-in voltmeter) used for the 5V motor supply instead. Chosen over MINI560 because MINI560 latches off on motor current spikes (documented issue, see Reddit thread in buck-converter-prompt.md). LM2596S rides through transient current spikes without latching.

**Inventory impact:** One XL4015 destroyed. Spare XL4015 still available for charging duty. LM2596S now assigned to 5V motor supply.

### 2026-08-20 — Battery monitoring + neck servos + fist tracking (full session)

#### Battery monitoring — main battery (Teensy A0)

**Wiring:**
- Voltage Sensor Module Max 25V (5:1 divider, 30kΩ/7.5kΩ)
  - Screw terminals: VCC → battery +, GND → battery -
  - 3-pin header: S → Teensy A0 (pin 14), + → Teensy 3.3V, - → Teensy GND
- Module confirmed: 12.6V battery → 2.52V on S pin (multimeter verified)

**Firmware:** teensy_microros.ino v0.3.1
- `analogReadResolution(12)` + `analogReadAveraging(8)` in setup()
- New publisher: `/teensy/battery_main` (std_msgs/Float32) at 1 Hz
- New console command: `BATTERY` (shows voltage, raw ADC, pin voltage)
- Battery voltage in heartbeat line: `bat_v=12.61`

**Bug found and fixed: Teensy ADC resolution mismatch**
- Symptom: ADC read 0.63V, multimeter read 2.5V on same pin
- Root cause: Teensy 4.1 defaults to 10-bit `analogRead()` (0–1023), firmware calculated with ADC_MAX=4095 (12-bit)
- Fix: `analogReadResolution(12)` in setup() — one line
- Lesson: Teensy 4.1 has 12-bit ADC hardware but defaults to 10-bit for Arduino compatibility. Always set explicitly.

**Debugging path:**
1. Initial reading 3.15V (0.63V on pin) — suspected floating pin / missing ground
2. Added ground wire — no change
3. Scanned all 18 analog pins — none read 2.49V
4. Repeated reads with delay — stable at 0.63V (ruled out impedance)
5. Disconnected S wire — A0 dropped (confirmed S is on A0)
6. Multimeter read 2.5V on S while connected to A0 — module works, ADC is wrong
7. Realised raw=782 ÷ 1023 × 3.3 = 2.52V — ADC was 10-bit, not 12-bit
8. Added `analogReadResolution(12)` — reading jumped to 12.61V ✅

**Verified end-to-end:**
- Console: `BATTERY main_v=12.608 raw=3129 pin_v=2.522` ✅
- ROS 2: `ros2 topic echo /teensy/battery_main` → `data: 12.61` ✅

#### Battery monitoring — UPS battery (INA219 via I2C)

**Discovery:** INA219 is on I2C bus 7 (address 0x41), NOT bus 1 as Waveshare wiki says. Jetson Orin Nano Super maps 40-pin header I2C to bus 7 (c250000.i2c).

**⚠️ Critical: Bus 7 is system-sensitive**
- Reading multiple INA219 registers in quick succession caused a **system reboot**
- Fix: Only read register 0x02 (bus voltage) — single read, nothing else
- The reboot was likely caused by I2C bus contention with system-critical devices on bus 7

**Reading:** `smbus.SMBus(7).read_word_data(0x41, 0x02)` → bus voltage = (raw >> 3) * 0.004

#### Battery bridge service (systemd)

**Script:** `~/robot-face/battery_bridge.py`
- Subscribes to `/teensy/battery_main` via rclpy (main battery)
- Reads INA219 register 0x02 on I2C bus 7 (UPS battery) — single read only
- Writes `/tmp/battery_status.json` every 3 seconds
- Voltage → percentage: 3S Li-ion, 12.6V=100%, 9.0V=0%

**Service:** `~/.config/systemd/user/battery-bridge.service`
- Starts after micro-ros-agent
- Restart=always
- Sources ROS 2 Humble environment

#### Control panel — battery display

**Flask endpoint:** `/api/battery` reads `/tmp/battery_status.json`
- Returns: `{"main_battery": {"voltage": 12.61, "percent": 100}, "jetson_battery": {"voltage": 12.57, "percent": 99}}`

**Panel UI:** Battery section in control.html with two bars (Main + Jetson), polls /api/battery every 3s

#### XL4015 destroyed by reverse polarity

- User repurposed XL4015 to step down 12.6V battery → 5V for motors
- Battery + and - accidentally reversed on XL4015 input → smoked immediately
- XL4015 has NO reverse polarity protection
- Battery confirmed OK at 12.5V (disconnected fast)
- LM2596S (with voltmeter) used instead — chosen over MINI560 because MINI560 latches off on motor current spikes (documented Reddit issue)
- Lesson: always verify polarity with multimeter before connecting any buck converter

#### Neck servos (pan/tilt gimbal bracket)

**Hardware:**
- 2× SG90 servos on DC Dual Servo Gimbal Pan/Tilt Bracket
- Power: LM2596S at 5V (battery 12.6V → 5V)
- Pan servo signal → Teensy pin 2
- Tilt servo signal → Teensy pin 3
- Common ground: LM2596S GND + Teensy GND + battery negative

**Firmware:**
- Arduino Servo library, `servoPan.attach(2)`, `servoTilt.attach(3)`
- Console commands: `SERVO pan=X tilt=Y`, `SERVO` (query), ~~`SWEEP`~~ (removed — too aggressive)
- Servo limits: pan 70-140°, tilt 60-120° (enforced in firmware with constrain())
- Tilt reversed in firmware: `servoTilt.write(SERVO_TILT_MAX + SERVO_TILT_MIN - pos)` — mount is flipped
- Home position: pan=110, tilt=90 (screen faces forward at this angle)
- Smooth motion: exponential easing (3% of remaining distance per loop iteration, ~1000Hz)
- servo.write() only called when integer position changes (reduces jitter)

**Panel UI:**
- Servo controls as floating overlay in top-right corner of video feed
- Arrow buttons (↑↓←→) + center button (●)
- Keyboard arrow keys supported
- Controls visible only when camera is enabled
- Position shown compactly: `110,90`

**Tilt servo incident:**
- The initial aggressive SWEEP test (0-180°) damaged the tilt servo
- The servo drove to the "down" position and locked there
- Prolonged stalling while debugging burned out the motor
- Root cause: 0-180° sweep exceeded the bracket's mechanical limits
- Lesson: Never sweep servos past the bracket's physical range. The SWEEP command was removed. Limits set to 30-150° initially, later refined to pan 70-140°, tilt 60-120° based on user testing.
- Replacement ordered: MG90S equivalent (metal gears, 2.2 kg·cm, same size as SG90)
- User opened the damaged servo, found internal damage, reassembled with reversed direction — tilt direction reversed in firmware to compensate

#### Fist tracking mode

**Feature:** When gesture detection is enabled and a closed fist is detected:
1. Face mood changes to "love" (😍)
2. Neck servos follow the fist — pan/tilt adjust to keep fist centered in frame
3. When fist disappears, mood restores to previous, tracking stops

**Implementation (panel JavaScript):**
- Gesture stream provides `d.is_fist` (boolean) and `d.pos.err_x`/`d.pos.err_y` (normalized error from center)
- On fist detected: POST `/api/state` with `mood: 'love'`, save previous mood
- While tracking: every 250ms, calculate servo correction proportional to error
  - `dP = -err_x * TRACK_GAIN` (pan, reversed because camera mirrors)
  - `dT = -err_y * TRACK_GAIN` (tilt)
  - Deadzone: ignore errors < 0.03 (prevents jitter)
  - Throttled to 250ms between corrections
- On fist lost: POST `/api/state` with saved mood
- Constants: TRACK_GAIN=30, TRACK_DEADZONE=0.03, TRACK_INTERVAL=250ms

#### Files modified this session

| File | Changes |
|---|---|
| `teensy_microros/teensy_microros.ino` | Battery ADC, servo control, smooth motion, tilt reversal, limits |
| `PINOUT.md` | Rebuilt from scratch for Teensy 4.1, A0 + pins 2/3 documented |
| `inventory.md` | 30SQ050 Schottky diode added, XL4015 incident noted |
| `robot-face/battery_bridge.py` | New — ROS 2 + I2C → JSON bridge |
| `robot-face/app.py` | /api/battery and /api/servo endpoints |
| `robot-face/templates/control.html` | Battery bars, servo controls, fist tracking |
| `~/.config/systemd/user/battery-bridge.service` | New systemd service |
| `servo-problem.md` | Diagnostic document for second opinion |
