# 056 — New step-down, sensor fixed, charging proven; the 45 W supply overloads; the Jetson drains flat

| | |
|---|---|
| **Date** | 2026-11-06 |
| **Type** | Repair + problems |
| **Status** | ✅ Hailege XL4015 at CV 12.60 V / CC 2.0 A · ✅ Voltage sensor on the motor pack, reads 12.10 V · ✅ Charge path proven (+56 mV in, −81 mV out) · ✅ Motor pack charged to 12.27 V · ✅ 45 W overload found, 90 W LEICKE bought · ⚠️ Whine with both on one supply (diagnosed 11-07, log 058) · ❌ Jetson UPS drained to empty overnight |
| **Severity** | High |

---

The same day's 2nd-floor work (health check, camera paths, arm relabel) is in log 057.

## 1. Setting the new XL4015

- **CV 12.60 V and CC 2.0 A**, both set with nothing connected. For CC the meter goes on its 10 A socket across the output; move the probe back to the V socket afterwards.
- **3 A instead of 2 A? No:**
  - The 30SQ050 Schottky is rated **3 A**: about 0.9 W at 2 A.
  - The supply also feeds the Jetson.
  - The board has no heatsink.
  - 3 A would save only about 30 min, because the end of a charge is the slow, tapering constant-voltage stage anyway.
  - **Never above 4 A**, the 40T cell's charge maximum.
  - 3 A would need a 5 A+ Schottky and a 90 W+ supply.
- **Different from log 011's plan:** that log set 12.60 V at the pack, after the diode. This time 12.60 V was set at the board, so the pack tops out one diode drop lower: **12.27 V**, about 4.09 V per cell, about 90 % (section 6). That's kind to the cells; noted so nobody "fixes" it by accident.
- **Log 011 had the 30SQ050 as 30 A; it is 3 A.** Corrected there.

## 2. BMS, DC jack, holder manual, cells

- **Charge LED off after wiring:** the red LED only lights when the board hits its 2 A limit. With the pack nearly full and a diode in the way, the current was far below that.
- **BMS photo:** it looked undamaged.
  - Pads: 0V (B−), 4.2V, 8.4V, 12.6V (= B+ = P+), ⊖ = P−; ⊕ unpopulated.
  - **The charge negative goes to ⊖ (P−), never the 0V pad**: that would bypass the BMS's protection.
  - One empty hole with bare copper near the top was never explained. Charging works.
- **DC jack:** check the polarity (centre +) with the meter before plugging in. −11.9 V would mean reversed, the mistake that killed the last board.
- **The Heltec holder's manual** (the AliExpress page hit a CAPTCHA, which wasn't solved; the seller's PDF was read instead):
  - short-circuit protection is "delayed self-recovery";
  - the 5.5 × 2.1 jack on their boards is a charge port;
  - cell over-charge cut-off **4.225 V**;
  - a cell above 4.0 V, or unbalanced cells, can block charging.
- **Cells:** 4.04 V each, balanced: about 12.1 V, ~80 %.

## 3. Voltage sensor fixed; the Teensy stuck in its bootloader

- **10:16:** the Jetson booted, but the hub showed nothing behind it and the Teensy was missing. The Jetson was on its own battery (UPS 12.23 V, −7.98 mV). The Teensy came back at 10:19, still reading `PINTEST pin=14 pullup=1054 … plain=0`.
- **11:00:** the user rewired the sensor straight to the motor pack ("fresh new connections from the sensor to battery").
- **The Teensy was sitting in HalfKay** (`16c0:0478 Teensy Halfkay Bootloader`, no serial port). Most likely the PROGRAM button got pressed, or a wire touched the PROG pin, during the rewire.
  - Recovered by flashing the existing hex: `teensy_loader_cli --mcu=TEENSY41 -w -v build/teensy_microros.ino.hex`.
  - micro-ros-agent reconnected.
- **Result:**
  - `BATTERY main_v=12.096 raw=3002 pin_v=2.419 pack_v=12.1 pack_from_id=1 source=a0`;
  - `PINTEST pin=14 pullup=3241 pulldown=2824 plain=3001`.
  - **The sensor reads the motor pack**, matching the servos (12.1 V) and the cells (3 × 4.04 V).

## 4. Proving the charge path, without draining the pack

- **The user's plan:** run the motors to drain the pack below 60–70 % and then watch it charge. **Not needed:** free-spinning wheels draw 0.1–0.3 A, and the motors are capped at 30 % / 3 s. The 1 mV sensor can see a charge start directly.
- **Logged every ~4 s:**

| Time | Pack | Event |
|---|---|---|
| 11:05:22 | 12.076 V | before |
| 11:05:27 | 12.132 V | supply in: **+56 mV** |
| 11:09:02 | 12.213 V | rising ~20 mV/min |
| after | 12.128 V | supply out: **−81 mV** |

**The whole path works:** step-down → diode → fuse → jack → BMS → cells.

## 5. The supply switches off: 45 W isn't enough

**Symptom:**
- The Jetson's charge cable (robot DC port → Jetson) made the supply cut out completely, needing a mains unplug to recover.
- The supply straight into the UPS worked.
- The supply into the robot's DC port with the Jetson cable unplugged worked.

**Tests:**
1. **Cable polarity:** 18.8 V the right way round, so it isn't reversed or shorted.
2. **Step-down disconnected:** the Jetson charged without issue: UPS 10.69 V −9.44 mV → 11.27 V **+14.19 mV**.

**The label:** NVIDIA / LiteOn **PA-1450-26, 19 V 2.37 A = 45 W**.

**Load with both charging:** Jetson + UPS charging ≈ 33 W, plus the step-down at 2 A ≈ 29 W, ≈ **62 W**.

**"But why did it shut down fully?"**
- Laptop supplies latch off on overload until the mains is removed.
- The converters draw constant power, so their current rises as the voltage sags.
- The UPS input's capacitors add a surge when plugged in live.

**Wrong turns:**
- First the supply was assumed to be 65 W.
- Then "turn CC down to about 1 A" was offered as a fix. On 45 W that still comes to ~48 W; it would need about 0.5 A, about 8 h a charge.

**Fix:** a 90 W supply.
- The Nobsound 90 W was fine, but its "universal 5.5 × 2.1–2.5" plug can sit loose in a 2.5 mm jack.
- **The LEICKE ULL 19 V 4.74 A 90 W (model NT00348) was bought instead:** it ships an exact 5.5 × 2.5 tip and has a 2-year warranty. It arrived on 11-07; check +19 V centre-positive with the meter before first use.

**Until then:** charge one pack at a time.

## 6. A whine, then the motor pack charges alone

**16:29–16:34, both packs on the 45 W supply:**
- The UPS had finished: its current tapered and stopped at 16:25, 12.64 V.
- The motor pack stepped **+0.54 V** at plug-in (11.334 → 11.874) and its reading wobbled between 11.97 and 12.10.
- **A high whine started**, rising after 2 minutes. The user unplugged.

**With the Jetson unplugged from the supply the whine stopped.** The assistant concluded it was "the 45 W supply at its limit, not the step-down". **That was wrong:** it came back on the 90 W supply the next day (log 058).

**Also corrected the same afternoon:** the wobble isn't pulsing current. At 2 A the step-down leaves ripple on the pack's terminals, and the ADC samples it at random points.

**Motor pack alone, quiet, from 16:36:**

| Time | Motor pack | UPS (Jetson on battery) |
|---|---|---|
| 17:00 | 11.842 | 12.10 |
| 17:30 | 12.177 | 12.02 |
| 17:50 | 12.257 | 11.86 |
| 18:20 | 12.265 | 11.58 |
| 18:43 | 12.273 | **11.40** |

The motor pack sat at **12.26–12.27 V from 17:50**: CV 12.60 V minus the diode, about 90 %. **Charge confirmed: 11.33 → 12.27 V.**

## 7. The Jetson drained to empty

- **18:43:** the Mac-side watcher fired on UPS ≤ 11.40 V. The user was asked to move the supply back to the Jetson.
- **21:08:** UPS **10.14 V** and still drawing ~1 A. The push notification only reached the terminal: "Mobile push not sent (Remote Control inactive)".
- The supply wasn't moved, and the Jetson shut off that night when its UPS cut out (log 058).
- **Logs on the robot:** `~/charge_log_20261106.csv` (13:08–21:08, every 30 s: `time,motor_v,ups_v,ups_shunt_mV`). Made by `~/charge_log.sh`; the shunt is read from INA219 register 0x01.
- **Tooling mistake:** `pkill -f charge_log.sh` matched the ssh command that ran it and killed the session. Find the PID with `pgrep` and exclude your own shell instead.

## Takeaways

- Add up the supply's loads before sharing it: 33 W + 29 W doesn't fit in 45 W, and laptop supplies latch off instead of sagging.
- A charger stage that stops one diode drop short of 12.6 V is a feature: ~90 % is gentle on the cells.
- An alert nobody sees isn't an alert. Charge-state alarms need to reach the user's phone, or the robot has to protect itself (shut down cleanly on low UPS voltage).
