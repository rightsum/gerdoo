# 052 — A drive motor spun as soon as the battery was connected

| | |
|---|---|
| **Date** | 2026-10-27 |
| **Type** | Problem |
| **Status** | ⚠️ Root cause not confirmed · ✅ 10 kΩ pull-downs on the EN pins (fitted for 0.5.0, log 046) · ✅ `driveSafePins()` first in `setup()` |
| **Severity** | High (an uncommanded wheel) |

---

Written on 2026-11-07 from the session transcript.

## Symptom

With the Teensy **not connected**, one drive motor spun as soon as the power pack was connected.

## Diagnoses offered

1. **Battery and motor swapped on the IBT-2's B± / M± screws.** The battery would then drive the motor through the bridge's body diodes, with no logic involved. A meter check was proposed.
2. **Undriven EN / PWM inputs.** With no Teensy, the IBT-2's EN and PWM inputs float, and the 74HC buffer can read a floating input as high. Later in the day it was described that way ("as one did yesterday").

**Neither was confirmed in the transcript.** (2) is the likelier one. The pull-downs went in for firmware 0.5.0, and no uncommanded spin has been reported since. That's not a controlled test, though, and nobody measured the inputs.

## What was done

- **Workaround until the parts came:** the yellow 20 A fuse was pulled out and used as the motor switch.
- **Fix:** 10 kΩ pull-downs on each driver's joined EN (ordered, arrived 2026-10-28). Spare voltage-sensor modules (7.5 kΩ) were suggested as stand-ins.
- **Firmware 0.5.0 (log 046):** `driveSafePins()` is the first call in `setup()`, so both bridges are disabled before anything else runs.

## Takeaways

- Every enable input on a power stage gets a pull-down to "off". The MCU being unplugged, rebooting or in its bootloader must never mean "on".
- Keep a way to cut motor power without tools (a fuse, a switch) until the logic side is proven.
