# 055 — The voltage sensor reads 0 V, the motor pack won't charge, and a reversed battery kills the step-down

| | |
|---|---|
| **Date** | 2026-11-05 |
| **Type** | Problems |
| **Status** | ✅ `PINTEST` command · ✅ Pack voltage from the servos as a fallback · ✅ Not charging: a loose wire · ❌ XL4015 #1 dead (battery connected backwards), spare dead too · ✅ Replacement ordered (fitted 11-06, log 056) |
| **Severity** | High |

---

## 1. Before closing the 1st floor: a checklist

The user had wired spare Teensy ports up to the next floor and didn't want to open the bottom again. The checklist given:
- ⚠️ **Voltage sensor reads 0 V.** Its screw terminal must be on the power pack's P+/P−, with S → pin 14.
- ⚠️ **Fuse colours** (log 051): 15 A blue on the servo feed, not the green 30 A; 20 A yellow on the motors; 30 A green on the power-pack main; 5 A tan on the electronics.
- ⚠️ **The LED-strip branch has no fuse.** Add a 2–3 A inline fuse on the MINI560 input.
- ⚠️ **10 kΩ pull-downs** on Teensy pins 7 and 21 (log 052).
- ⚠️ **Charger:** a diode on the XL4015 output with the band towards the battery, about 2 A. Not measured yet.
- ⚠️ **The Jetson restarting by itself** (log 053): check the UPS input and the electronics-pack connector crimps.
- **Serviceability:**
  - a main switch per pack that can be reached with the floor closed;
  - reachable fuses;
  - strain relief on wires going up.
- **Spares to bring up:** GND + 3.3/5 V, and A2 (pin 16) for a second voltage sensor.

## 2. "Is it charging?": the Jetson's own supply

- **What happened:** the user plugged in the 19 V supply. The UPS INA219 (bus 7, 0x41) swung from −8.9 mV (discharging about 0.8 A) to **+14.03 mV (about +1.4 A in)**, and the UPS pack rose 11.59 → 12.20 V in 6 minutes.
- **Wrong turn 1:** the assistant concluded the robot's charger feeds the electronics pack. It doesn't. **The supply was plugged into the Jetson's UPS board, which charges its own pack.** The user: "the charger is for the jetson itself, not the ups of jetson".
- **Wrong turn 2:** at 12.668 V and still +12.8 mV, the assistant raised a false alarm ("unplug the charger now … past 12.6 V"). It was the UPS board's own charge profile; nothing was overcharging.
- **Learned:**
  - The panel's "12.6 V / 100 %" during charging is the charger's voltage, not the state of charge.
  - Charging detection for the panel and the reactor screen was offered.
  - **The motor pack's only charge route is DC jack → XL4015 → diode → pack.**

## 3. The voltage sensor reads 0 V

**Evidence:**
- A0 (pin 14) read raw 0–2, steady.
- The user: S → 14, − → Teensy GND, + → nothing (correct: that pin is unused), screw terminal "to + and − of the battery". The 12 V was taken from the MINI560's input pins, deep in the robot.
- `STRIP 100` → `duty=4091/4095` and "the LED worked fine", so the MINI560 input has power.

**New firmware command `PINTEST <pin>`** (pin 14 or 16–27). It reads the pin with a pull-up, a pull-down and no pull:

| Pin | Reading | Meaning |
|---|---|---|
| 14 | `pullup=1037 pulldown=0 plain=0` | ~0.84 V with the pull-up: the module's 7.5 kΩ leg to ground, **no input voltage** |
| 16 (free) | `pullup=4093 pulldown=29 plain=985` | A floating pin, for comparison |

**Conclusion:** the S wire and ground are fine. Nothing reaches the module's screw terminal. It was fixed on 11-06 (log 056).

**Fallback: the pack voltage from the servos.** The user asked, "so we can read the voltage from servos? so technically we don't need the voltage sensor?"
- The STS3215 reports its supply in register 62, in 0.1 V steps.
- The firmware reads it from IDs `{21, 22, 1, 11}` every 5 s. The neck servos go first: they're idle, so they sag least.
- `batteryMainV` = A0 when A0 reads above 3.0 V, otherwise the servo value.
- `BATTERY` now prints `pack_v`, `pack_from_id`, `source=servo|a0`.
- The first build failed (`'powerPackV' was not declared in this scope`). Fixed by moving the globals; flashed.
- **Result:** `BATTERY main_v=11.900 … pack_v=11.9 pack_from_id=1 source=servo`, and the panel showed 11.9 V / 81 %.
- `BUS SCAN` found 16 servos; **the neck (21, 22) is missing**, its branch unplugged.
- These builds still said `microros-0.5.0`; 0.5.1 came the next day (log 057).

## 4. The motor pack doesn't charge

- `pack_v` stayed at 11.9 V with the charger plugged into the robot.
- Raw register reads: ID 1 `… 00 77 …` = 11.9 V; ID 11 `… 00 78 …` = 12.0 V. ID 21 didn't answer.
- **Causes listed:**
  - no 19 V at the XL4015;
  - the output diode backwards;
  - CV at or below the pack voltage;
  - wired to the wrong pack.
- **Root cause (found by the user): "there was a loose wire to the battery from step down".**

## 5. The battery connected backwards killed XL4015 #1

**What happened:** fixing the loose wire, the user "accidental connected briefly the battery negative to positive of step down and positive of battery to negative of step down". Afterwards the output read **1.43 V**, then 1.18, then 0.82 V with the input unplugged, and the red LED stayed on.

**Diagnosis:**
- **Not just the diode.** A shorted diode would show the pack's ~12 V; an open one the 12.6 V set point.
- On these CC/CV boards **OUT− returns to ground through the R050 current-sense resistor**. With the pack's + on OUT−, current flowed backwards through it and the current-limit circuit. That path, or the op-amp, is damaged.
- **The red LED is the current-limit indicator.** Lit with no load, it means a fault.
- A slowly falling 1.18 → 0.82 V is capacitors discharging, not regulation.
- **The board is finished. Never charge lithium with it again.**
- **The spare was already dead** ("i already fucked the spare"); when it died isn't recorded.

**Replacement:** a Hailege 3-pack of XL4015 5 A CC/CV boards (two pots, 470 µF / 35 V caps) was approved.
- **Setup procedure:**
  1. 19 V in, nothing on the output.
  2. CV 12.60 V.
  3. CC 2.0 A, with the meter on its 10 A socket across the output.
  4. The red LED must be off at no load.
  5. Then OUT+ → diode (band to the pack) → 5 A fuse → XT30 → P+.
- **Never charge from the LM2596S or MINI560:** they have no current limit.

**Prevention:** a 5 A fuse and a polarised XT30 on the charge lead, so the pack can't be connected backwards again.

## Takeaways

- A steady 0 on an ADC pin with a divider module is "no input", not "no wiring". Pull-up/pull-down tests tell the two apart remotely.
- The servos already measure the pack, so every servo is a free voltmeter.
- On a CC/CV buck, a reversed battery doesn't just stress the diode; it runs backwards through the current-sense path.
- Find out which supply a "charger" is plugged into before reading anything into a current.
