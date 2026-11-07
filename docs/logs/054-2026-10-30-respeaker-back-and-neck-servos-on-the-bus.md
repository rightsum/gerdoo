# 054 — reSpeaker back, and the neck servos on the bus

| | |
|---|---|
| **Date** | 2026-10-30 |
| **Type** | Bring-up + fix |
| **Status** | ✅ Mic/speaker loopback passes · ✅ Neck servos IDs 21/22, spliced into one arm's trunk, 18 servos found · ✅ Console commands start with a newline, 224 tests · ⏳ Neck limits, `NECK` commands, first move |
| **Severity** | — |

---

Written on 2026-11-07 from the session transcript.

## 1. The reSpeaker came back; loopback test

- **13:58:** the Jetson was again found freshly booted (`up 0 min`, log 053). Still no reSpeaker.
- **14:01**, after the user replugged it: `Bus 001 Device 049: ID 2886:001e Seeed … reSpeaker Flex XVF3800 C16K6Ch`, ALSA `card 2: C16K6Ch`. Device number 49 means many re-enumerations. **What the user changed isn't recorded.**
- **The test**, four rounds of:
  1. a 1200 Hz beep;
  2. `parecord` for 5 s, 6 channels at 16 kHz;
  3. `sox … remix 1` (channel 0, the XVF3800's processed output);
  4. a 600 Hz beep;
  5. playback.

| Round | RMS | Peak | Quietest 0.1 s | Loudest 0.1 s |
|---|---|---|---|---|
| 1 | −44.2 | −17.4 | −79.6 | −27.7 dBFS |
| 2 | −23.0 | −6.4 | −58.8 | −16.7 |
| 3 | −18.7 | −1.1 | −80.7 | −12.5 |
| 4 | −27.1 | −6.8 | −85.5 | −18.4 |

- **Noise floor** about −80 dBFS.
- **Round 3** was close to clipping.
- **Round 1** was ~10 dB low: a late start, or the AGC settling.
- **The user:** "yeah it was good !".
- **Open:** why it dropped off USB on 10-29.

## 2. The neck servos join the arms' bus

**Plan:**
- same bus (Waveshare adapter on `Serial7`), new IDs 21 and 22, set with the arms unplugged;
- a Y-splice or an STS hub;
- Feetech 5264-style plugs, since Futaba/JR won't fit.

**First scan, pan alone, failed:** `console.py "BUS SCAN 7"` returned `ERR unknown_command HEARTBEAT seq=23 …`. The command reached the Teensy glued to a half line of echoed heartbeat text.
- **Workaround:** `stty -F /dev/serial/by-id/usb-Teensyduino_Dual_Serial_…-if00 raw -echo 115200`.
- **Fix:** `teensy_microros/console.py` and `robot-face/teensy.py` now send `"\n" + cmd + "\n"`. The leading newline ends any half line left in the Teensy's buffer when the port opens. 224 tests pass on the Jetson; deployed.

**IDs:**

| Step | Console reply |
|---|---|
| Pan alone | `BUS id=1 model=777 pos=3931 volt=12.4` |
| Set pan | `BUS SETID 1 21` → `ok 1 -> 21 (reads back id=21, old id silent)` |
| Tilt | Couldn't be unplugged from pan, so it was scanned chained behind it (`ids=1,21`), then `BUS SETID 1 22` |
| Result | `21 pos=3547`, `22 pos=954`, 12.4 V |

**Wiring (the user's plan, approved):**
1. Cut one arm's plug.
2. Run a long 3-wire from the neck to that arm's base.
3. Y-splice it there and refit the plug on the adapter.

Advice that came with it:
- match the wires by pin position, not colour;
- check continuity;
- heat-shrink each joint;
- put the splice on a part that doesn't rotate, with a screwed strain relief;
- 22–24 AWG, away from the motor wires.

That trunk now carries an arm plus the neck. The stock cable is good for ~2–3 A.

**19:02, "confirm you see 18 servos":** `found=18 ids=1,2,3,4,5,6,7,8,11,12,13,14,15,16,17,18,21,22`, 12.0–12.3 V, 27–29 °C, torque off, no errors.

**Labels:** that day the assistant called IDs 1–8 the left arm and 11–18 the right. On 2026-11-06 firmware 0.5.1 relabelled them: **left = 11–18, right = 1–8** (log 057). Which ID group's trunk carries the neck splice isn't recorded.

**Open:**
- neck limits (pan ±90°, tilt −15°…+30° planned);
- Teensy `NECK` commands;
- a panel card;
- the first powered move.

On 2026-11-06 the neck servos didn't answer: their branch was unplugged while the 2nd floor went on.

## Takeaways

- Any line-based console that shares a port with streaming output should open each command with a newline.
- New servos all ship as ID 1, so set them one at a time. Once the first has moved off ID 1, the next one can join the bus, even chained behind it, and be changed in turn.
