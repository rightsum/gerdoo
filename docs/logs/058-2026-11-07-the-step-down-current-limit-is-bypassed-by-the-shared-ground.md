# 058 — The whine: the step-down's current limit is bypassed by the shared ground

| | |
|---|---|
| **Date** | 2026-11-07 |
| **Type** | Problem + design decision |
| **Status** | ⚠️ Diagnosis strongly supported, not yet proven with an ammeter · ✅ Rule: never charge the motor pack while the Jetson is on the same supply · ✅ Replacement charger ordered (3S 1 A board) · ⏳ Arrival check, fit, one logged full charge · ⚠️ `ups_display.service` failing · ⚠️ Motor pack drains itself overnight |
| **Severity** | High (over-current through signal grounds; unattended charging inside a closed floor) |

---

## 1. After the Jetson ran flat

- **The 90 W LEICKE supply arrived** and the Jetson booted from empty (log 056).
- **No step-down recalibration needed:** the XL4015 holds the voltage and current set by its pots for any input above ~15 V, and the new supply gives the same 19 V.
- **Jetson health after the hard power-off:**
  - up 3 min, no ext4 / fsck / I/O errors, disk 5 %;
  - `micro-ros-agent`, `robot-face`, `reactor-screen` active.
- **`ups_display.service` failed**, the UPS board's small OLED:

  ```
  ExecStart=/bin/sh -c python3 -m ups_display.display_server (code=exited, status=1/FAILURE)
  … Adafruit_SSD1306 … _initialize → Adafruit_PureIO … write_byte_data
  OSError: [Errno 121] Remote I/O error
  ```

  - Nothing answers at the OLED's I2C address.
  - **Cause (the user, later that day):** the OLED's connector wasn't fully seated. Pushing it in fixed it. The service gave up after 5 fast failures, so it needs `sudo systemctl restart ups_display` once (sudo needs the user's password).
  - The failure is stamped "Fri 2026-11-06 21:29:51" because the Jetson has no RTC: a boot starts at the last saved clock until NTP syncs. Early-boot timestamps are wrong.
- **The journal isn't persistent:** `journalctl --list-boots` shows one boot. Earlier power-offs (log 053) can't be examined. Consider `Storage=persistent`.
- **New charge log on the robot:** `~/charge_log.csv` (the previous one renamed to `~/charge_log_20261106.csv`).

## 2. The motor pack drains itself

**12.18 V at 21:08 (resting) → 11.05 V at 08:55**, with the servo reading 10.9 V. That's about half its charge in 12 hours, with the robot "off".

- The servos and whatever else hangs off the power pack stay powered.
- The load hasn't been measured: about 130–170 mA on average if the pack holds ~1.6–2 Ah of that.
- **Action:** a main switch on the power pack (it's on the pre-close checklist), or unplug it when parked.

## 3. The whine comes back on the 90 W supply

**Symptom:** with both packs on the new supply, "it's charging but the sound is back ... and it's increasing i believe it's from jetson".

**Wrong turn (11-06, log 056):** the whine had been blamed on the 45 W supply at its limit. It happens whenever the step-down and the Jetson share **any** supply.

**Second wrong turn (that morning):** the assistant said the motor pack wasn't charging, guessing the supply was on the Jetson only. The log shows it rising ~45 mV/min (11.024 → 11.117 V in 2 min), so both were already connected.

**Mechanism:**
- The XL4015 measures its charge current on the **negative side**: the R050 (0.05 Ω) between IN− and OUT−. Its current loop only sees current that returns through that resistor.
- **In this robot those two negatives are joined elsewhere too.** With the Jetson on the same supply, there's a second way back to the supply's negative:

```
supply + → step-down → diode → motor pack + … motor pack −
   intended return:   step-down OUT− → R050 (measured) → IN− → supply −
   accidental return: sensor/servo-adapter GND → Teensy GND → USB ground
                      → Jetson GND → UPS → Jetson DC jack − → supply −
```

- The loop measures less than flows, so it lets more through.
- With the Jetson unplugged from the supply, the accidental path is open and the 2 A limit works. That explains the quiet charge on 11-06.

**Evidence:**
- **Whine only with both on one supply:** with both the 45 W and the 90 W supply.
- **Step at plug-in:**
  - with the Jetson on the supply, **+0.54 V** (11.334 → 11.874);
  - without, +0.15 V at first, +0.29 V after 2 min (11.500 → 11.649 → 11.790).
  - That suggests roughly 1.5–2× the current, i.e. ~3–4 A, which is over the 30SQ050's 3 A.
  - It fits the 45 W supply tripping on 11-06 too. That isn't proven.
- **Others hit the same thing:**
  - [EEVblog](https://www.eevblog.com/forum/beginners/constant-current-control-with-dc-dc-step-down-module/msg1390680/): a CC module only regulated with the load's negative on OUT−; "the current sense … is internally connected between OUT- and IN-", and with a shared ground it runs unlimited.
  - [Arduino forum](https://forum.arduino.cc/t/using-constant-current-buck-converter-with-common-ground/861109): the same worry for charging with a shared ground; no module solves it.
  - [ProtoSupplies](https://protosupplies.com/product/5a-adjustable-step-down-cc-cv-module/): "0.05 ohm resistor … between the '-' terminals of the input and output".
  - [TI SLUA066](https://ti.com/lit/pdf/slua066): high-side sensing lets "the charger, the application, and the battery" share a common ground.

**Not done yet (the proof):** put the meter on its 10 A range in the charge lead and read it with the Jetson off the supply, then on. Over 2.0 A with the Jetson on confirms it.

**"Where is the ground link? I haven't connected the Teensy's ground to the main pack."**
- There's no dedicated wire. The **16 AWG link between the two packs in `inventory.md`'s ground plan (log 048) isn't built**, and the assistant was wrong to assume it was.
- Signals still join the grounds: the voltage sensor (input − and output − are one pin on these modules) and the servo adapter's serial ground, possibly the IBT-2 header GND and the LED-strip board. Both work, which proves a common reference.
- **Meter check, open:**
  1. Robot on batteries, supply out.
  2. Measure Ω between motor pack P− and Teensy GND. Expect about 0.
  3. Unplug the candidates one at a time to see which one carries it.
- Either way the robot needs a shared ground for its signals, so the charger has to change, not the ground.

**Worst case if left as is** (the extra current only flows while the pack is low, ~1–2 h per charge):
1. Teensy USB drop-outs or resets, possibly mid-arm-move.
2. A thin signal ground or USB cable overheating inside the closed floor.
3. The step-down or diode burning out; a diode that fails short removes the reverse protection.
4. A damaged USB port.
5. Fire. That needs two failures, since the BMS cuts at 4.225 V per cell, but unattended charging in an enclosed floor makes it worse.

**Ideas that don't work:**
- **Another diode in the step-down's OUT−:** either way round, it makes the accidental path the easier one. Diodes can't go in signal grounds.
- **The Teensy through the USB hub:** an ordinary hub passes ground straight through.
- **A USB isolator (ADuM3160):** it would remove one path, but the sensor and servo grounds remain.
- **Any other XL4015/XL4016/LM2596 CC module, and most XY-series digital bucks:** same negative-side sensing.

## 4. The replacement charger

**Requirement:** current measured on the **+ side** (or an isolated output), 19 V in, 3S 12.6 V, about 1–2 A.

| Candidate | Verdict |
|---|---|
| CN3703 boards | Right chip, but amazon.de sells only the bare IC |
| Ausla MPPT 5 A (CN3722, B0HPH6R4P2) | High-side, 8–28 V in, but fixed 5 A (≈ 63 W into the pack, too much for the supply with the Jetson and for the 40T cells). Usable only after swapping its sense resistor 0.024 → 0.060 Ω (I = 120 mV / R) |
| USB-C step-up 3S boards (Hailege B0CJY5LGRQ, Adeept, …) | ❌ Boost from 5 V. On 19 V they'd die, or pass ~18.5 V straight to the pack |
| Tbest B09TWBHRZJ | ❌ Lead-acid (14.8 V) |
| Separate isolated 12.6 V 2 A wall charger | Works (isolated output), but a second plug complicates the dock |
| **YWBL-WH "Li-Ion Charging Module Multicell 3S-1A"** (B07SG1RB1Q, €10.67) | **Ordered.** Input 14.8–23 V for 3S, 1S/2S pads open = 3S, I = 0.025 / R (R050 + an empty parallel spot), SS34 input diode, LED on / blinking / off when full |

The user confirmed this listing (B07SG1RB1Q).

**Arrival check:** the photos don't show which side its R050 is on.
1. Meter on continuity, nothing connected.
2. Probe **B+** against each end of the R050. A beep means it senses on the + side, which is good.
3. No beep there, but beeps to B−: negative side, same problem. Return it.
4. Check that the 1S and 2S pads are open, and the charge current (two R050 = 1 A).

**Wiring:**
- supply → UIN / GND;
- B+ / B− → the pack's **P+ / P−**;
- **leave out the 30SQ050**: the board's SS34 covers a reversed supply, and without it the pack reaches a real 12.6 V;
- XT30 and a 5 A fuse on the battery side.

1 A takes about 4–5 h from empty.

**Before closing the floor:** log one full charge with the Jetson on the same supply. It should stop at ~12.6 V with the LED off, and no whine.

**Until then:** charge the motor pack only while the Jetson is unplugged from the supply.

## Takeaways

- **A current limit only limits what it measures.** On a negative-side-sensing converter, any shared ground in parallel with the sense resistor makes the limit lie. Check where a module senses current before using it in a system with a common ground.
- A sound that appears only when two things share a supply means current is taking a path you didn't draw. Look for the second path before blaming the supply.
- When a fix is "obvious" (bigger supply), test it against the original symptom before calling it the cause.
