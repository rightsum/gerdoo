# 046 — Wheels and ultrasonic sensors: firmware, first tests, a panel card

| | |
|---|---|
| **Date** | 2026-10-28 |
| **Type** | Bring-up |
| **Status** | ✅ Firmware `microros-0.5.0` flashed · ✅ All 4 ultrasonic sensors answer · ✅ Both encoders count · ✅ Both motors ran (15%, 1 s) · ✅ Panel card "Wheels & ultrasonic" deployed, 189 tests pass · ⏳ Directions not yet confirmed by eye · ⏳ Counts per wheel turn not measured |
| **Severity** | — |

---

Wiring as in `inventory.md` (Teensy full pin map, 2026-10-27).

## Firmware (`teensy_microros`, 0.5.0)

**Motors:**
- **Pins:** two IBT-2s on PWM 5/6 and 22/23 at 20 kHz. Each board's joined EN is on 7 or 21, with a 10 kΩ pull-down.
- **Off at boot:** `driveSafePins()` is the first call in `setup()`, so both bridges are off before anything else runs.
- **Test limits:** at most **30%** and **3 s** per run, and each run stops by itself. Duty ramps at about 30% per 0.3 s.

**Encoders:**
- On the RT1062's hardware quadrature decoders (`QuadEncoder`): channel 1 = left (30/31), channel 2 = right (0/1).
- 22 k pull-ups, and a ~1 µs glitch filter against the motor PWM.

**Ultrasonic:**
- The 4 sensors fire one at a time, each in its own 60 ms slot. That prevents cross-talk and matches the HC-SR04's own minimum cycle. A full sweep takes 240 ms.
- The echo is timed by interrupts, so nothing blocks.
- The ECHO pins have pull-downs. A sensor that never answers then reads "silent" (power or wiring) rather than noise.

**Console commands:**

| Command | What it does |
|---|---|
| `MOTOR <L\|R> <-30..30> [ms]` | One timed run |
| `MOTOR STOP` | Stop both now |
| `ENC`, `ENC ZERO`, `ENC WATCH <s>` | Encoder counts |
| `SONAR`, `SONAR WATCH <s>` | Distances |
| `IO` | Pin levels |
| `DRIVE` | One line for the panel: run, duty, encoders, sonar |

**Build notes:**
- The `Drive` struct lives in `drive_types.h`, for the same reason as `arm_types.h`: the Arduino build puts a prototype of every sketch function above the types in the `.ino`.
- A templated ISR fails with "template with C linkage". The generated prototypes land inside the transport's `extern "C"` block. So the four ISRs are written out by hand.

The previous build is backed up on the robot as `~/teensy_microros_backup_20261028.hex`.

## First tests

| Check | Result |
|---|---|
| EN pins at boot | 0 and 0 |
| Ultrasonic, untouched | FL 12.8 cm steady, FR 42–45, BL 173, BR jumping 16–62/far |
| BL with a hand in front | 173 → 12–20 cm ✅ |
| Encoders, hand turn "forward" | L −366, R +480 (mirrored motors, as expected) |
| `MOTOR L 15 1000` | enc −29: same sign as the hand's forward turn |
| `MOTOR R 15 1000` | enc −122: opposite to the hand's forward turn |

**What the tests show:**
- **Direction:** + (RPWM) drives the left wheel forward and the right wheel backward, going by the encoder signs. The user still has to confirm that by eye.
- **15% is barely enough to move the wheels.** That's about 1.8 V average.
- **FL's steady 12.8 cm and BR's jumping** may be the covers' bottom edge. Log 049 found that the inner beams graze it; the plan is to handle that in software.
- **The hand turns weren't exact**, so the counts per wheel turn are still unmeasured.

## Panel: "Wheels & ultrasonic" card

**Routes** (password required, like the arms):
- `GET /api/drive`
- `POST /api/drive/run`, which checks side, ±30% (not 0) and 100–3000 ms before the Teensy sees it
- `POST /api/drive/stop`
- `POST /api/drive/zero`

**The card:**
- **Ultrasonic:** the 4 distances in a front/back layout, with bars (red < 20 cm, amber < 50 cm). It shows "far" and "silent" as words.
- **Wheels:** each wheel's state and encoder count. After a run it shows the count change and an approximate counts/s.
- **Controls:**
  - Power (−30…+30%) and time (0.2–3 s) sliders;
  - Run left and Run right;
  - STOP and Zero encoders.
- It polls 4 times a second while open, and **closing the card stops the motors**.

**Tests:** `tests/test_drive_routes.py` (15) covers parsing, the limits checked before the Teensy, refusals, login and password. 189/189 pass on the Jetson. Deployed with `deploy.sh`.

## Still open

- **Directions by eye**, for each wheel.
- **Counts per wheel turn** (a marked full turn by hand). That turns counts into distance.
- **Cover-edge echoes** on the inner beams: a minimum range or a per-sensor ignore band.
- **ROS topics** for the encoders and ranges, and real drive commands (both wheels, with the left/right sign flip), once the above are known.
- The **main battery voltage** reads 0 V: the voltage sensor's screw terminal isn't on the pack.
