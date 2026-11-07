# 050 — Charge-path diodes, board wiring, and a mis-logged topple

| | |
|---|---|
| **Date** | 2026-10-25 |
| **Type** | Design decision + wiring + correction |
| **Status** | ✅ Diode plan, wired · ✅ D4184 / voltage sensor / ultrasonic pins in `inventory.md` · ✅ Log 042 corrected |
| **Severity** | — |

---

Written on 2026-11-07 from the session transcript. Only `inventory.md` had these.

## 1. Diodes in the XL4015 charge path

**Input diode** (the user's, band toward VIN+): correct, but it only stops the board backfeeding the plug. If the DC jack and the dock's pogo pins both feed the charger, each input needs its own diode.

**Output diode, recommended:** OUT+ → diode → band → pack +. It stops the pack draining back into the XL4015 when there's no input.

- Two diodes are fine: about 0.7 W + 0.9 W of heat at 2 A.
- Set the XL4015's voltage **at the output diode's band end, with the pack disconnected**. The plan said 12.3 V there; on 2026-11-06 the new board was set to 12.60 V at its own output instead (log 056), so the pack tops out about one diode drop lower.

**Correction made that day:** the assistant had called the part "30SQ045 … 30 A". The **30SQ050 is a 3 A** Schottky. `inventory.md` was fixed. At a 2 A charge it runs near its rating, which matters for log 058.

## 2. Board wiring (D4184, voltage sensor, ultrasonic)

Recorded in `inventory.md`:
- **D4184 LED-strip MOSFET:** PWM from Teensy pin 4.
- **Voltage sensor (30 k / 7.5 k, ÷5):**
  - S → A0 (pin 14);
  - − → Teensy GND;
  - **+ → nothing** (on these modules the + pin isn't the measured input);
  - the screw terminal goes on the pack's P+ / P−.
  - Its maximum is 16.5 V, so it must never sit on the 19 V side.
- **HC-SR04P:** TRIG/ECHO on pins 33–40, powered at 3.3 V.

The empty + pin came up again on 2026-11-05 ("+ connected to nowhere … maybe that's the issue?"); it wasn't the issue (log 055).

## 3. Log 042's "second topple" was the neck, not the front cover

- The user reported "for the second time this part … hits by the nozzle and falls". The assistant assumed the front cover, built front cover v7 (±40° braces) and wrote the "Second topple, at ~80 % (2026-10-25)" section of log 042.
- The user then said it was the **neck**. The real fix (the head yoke printed on its back) is in log 035 (`gerdoo_neck_lidar_v3_A1.3mf`, 7 h 4 min).
- **Log 042 has been annotated.** Front cover v7's braces are harmless, so the cover plate was left as it is.

## Takeaways

- A part's current rating: read the datasheet, not the part number. 30SQ050 = 3 A, 50 V.
- When a print fails, ask which part before redesigning one.
