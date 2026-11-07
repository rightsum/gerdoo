# 032 — Measurements in, the dock's sign, and whether to turn the arms outward

| | |
|---|---|
| **Date** | 2026-10-17 (open) |
| **Type** | Design changes from measured parts, plus one open decision |
| **Status** | ✅ Measured parts applied to the models, the dock and the simulator · ✅ Caster blocks are one solid with the plate · ✅ **Arm mounts turned 70° outward** (the user's choice); the arms are still drawn and rest facing front · ✅ Hub on the vendor's 58 × 49; no light-dial pot |
| **Severity** | Low |

---

Follows [031](031-2026-10-16-simulator-physics-dock-and-assembly-fixes.md).

## What the user measured or confirmed

| Part | Value | Applied to |
|---|---|---|
| Heat-set inserts | the panels' standard, **Ø4.4** (through, or 7 deep blind) | every new M3 insert hole: radial cover inserts in all three plates, speaker. The old 4.2 × 6 is gone |
| Tyres, casters, floor gap | already proven in the last print | nothing touching them was changed. The 1.3 mm "caster mismatch" came from my estimated tyre |
| KA009 light strip | 300 × 1 mm, board 13.7 × 9.9, 220 mA (Bambu product page) | the 1.3 mm groove stays |
| DC-022B jack | thread **7.2** | Ø7.5 holes |
| Pogo pins | length **19.9**, plunger Ø**3.4** | pin protrusion setting (below) |
| Copper plates | **43.7 × 34.2** copper-clad, assumed 1.6 thick | the dock's contacts; the pins moved to ±20 |
| Treedix breakout | **62.2 × 37.0** | `tb_hole_dz` / `tb_hole_dx` in `1st-layer-v4` |
| HC-SR04P | "standard" | bosses on 42 × 17 |
| Speaker | ALMOCN 2" (2.08"), 18 g | fit study, mass model |
| USB hub | vendor drawing: 4× Ø2.8 (M2.5) on 58 × 49, board 65 × 56 × 19.6 | Ø2.1 pilots for M2.5 standoffs. ⚠️ The drawing's 49 disagrees with the measured 50.2 |
| WiFi antennas | 105 mm, RP-SMA | already modelled at 110 |

## Changes

**Robot back cover:**
- **Pogo pins** moved from x ±12 to **±20**, sleeves with them, so they land in the middle of the 34.2 mm plates.
  - Sideways tolerance at docking grows from about ±4 to about **±17 mm**.
- **DC jack.** It was wrongly removed for a moment ("remove the back hole" meant the dock's back), then put back between the pins as a Ø7.5 hole.
- **Pin protrusion:**
  - The pins must stick out at least 3.6 mm past the recessed dock floor to reach the plates at the stop pads.
  - Set them to **5.0–5.5 mm** for 1.4–1.9 mm of compression.
  - Of the 19.9 mm length, 11.6 mm sits in the shell and sleeve, and the rest pokes out of the sleeve's back for the wire.

**`charging-dock-v1`:**
- **Contacts:** two pockets 34.5 × 44 with a flat floor, so the plate faces sit at z −129.85.
  - Two Ø2.5 pilots per plate, for countersunk M3 self-tap screws at its top and bottom, clear of the pins' path.
  - A Ø4 wire hole at the lower outer corner into the hollow.
- **Cradle** raised to 115 mm so the 43.7 mm plates fit. It is still 39 mm under the antenna brackets.
- **19 V input** moved from the back wall to the **left side wall, as seen facing the dock**:
  - Ø7.5 hole with a Ø13 counterbore inside, leaving a 3 mm panel.
  - 37 mm above the floor, opening into the hollow.
- **Sign head** at the C1's scan height: 220 × 68 × 52, y 284–352.
  - **Lidar marker:** a 120° V, 120 wide and 34.6 deep, between two ribs (12 wide, 14 proud, at x ±81), in a 24 mm band centred on the scan plane.
  - **Why not a plain 90° V:** to a lidar it looks exactly like a room corner. Rib, gap, V, gap, rib is a shape rooms don't make.
  - **What the robot can read from it:** the V's apex gives the sideways offset, and its two faces give the yaw.
  - **Optional:** retro-reflective tape on the V faces. The C1 reports intensity, which makes the marker stand out further.
- **"GERDOO"** in Arial Black capitals, 24 mm tall, above the marker band.
  - At 385–413 mm above the floor it shows over the docked robot's lidar, whose top is at 382 mm.
  - Six separate letter bodies, 1.6 mm thick, for a second filament colour. They sit in a 0.6 mm recess and stand 1.0 mm proud.
  - D, R and O keep their counters.
  - If the letters print tight, slice them with about −0.08 mm XY compensation.
  - Fusion shows a reference warning on the letter extrude; the bodies are correct.
- **Clash check:** cradle, fin, sign and letters against every robot body: 0 mm³.

**`1st-layer-v4`:**
- **Caster blocks** (Body2/3) merged into the plate, with **3 mm root fillets** (7 of the 8 junction edges took them). Strength there matters, so they print as one solid now.
- **Ultrasonic bosses** shortened to 7.75 mm. The board now sits 10.75 mm behind the can holes, so the transducers stand 1.25 mm proud.
  - That matches the placeholder board, which the old bosses cut into by 1.25 mm.
  - It also keeps the hole edge out of the transducers' near field.
- **Tidy-up:** the leftover vertical tab inserts from log 030 are removed, in this plate and in the 2nd floor.
- **Known overlaps, unchanged:**
  - The drive placeholder's brackets overlap the motor pockets by about 3 mm. That's the estimated placeholder; the real brackets already fit the printed plate.
  - `Fillet3`, an original v3 feature, uses cached geometry after lost edge references.

## Fitting the Bambu A1 (256 × 256 × 256)

The sign fin was 310 mm tall, too tall for the A1. It is now two parts:

- **Mast** (200 × 182 × 50)
- **Head** (220 × 153 × 66)

The split is at y 200. The two parts join with a 25 mm **half-lap**: the mast's back half carries on up as a tongue, and the head is relieved to take it with 0.15 mm clearance. Two M3 screws go in from the back through the tongue into Ø4.4 × 5 inserts in the head.

**Every printable part, checked against the A1:**

| Part | Size (mm) |
|---|---|
| 1st layer | 250 × 235 × 43 |
| 2nd floor | 250 × 210 × 10 |
| 3rd floor | 250 × 178 × 10 |
| Front cover | 181 × 177 × 41 |
| Back cover | 175 × 96 × 39 |
| Arm bases | 113 × 95 × 90 |
| Dock cradle | 230 × 167 × 115 |
| Sign mast | 200 × 182 × 50 |
| Sign head | 220 × 153 × 66 |
| Lidar holder | 103 × 56 × 56 |

The rest are small. **All fit.** The three 250 mm plates leave only 3 mm a side: no brim or skirt.

## Turning the arms outward (decided: 70°)

The user's question: since an arm can't swing in over its own body, should the
mount turn 90° outward so J1's ±89° covers the outer 180°?

The simulator's sweep checks the left arm with J1 freed to ±180° (+ is outward)
against the body, the other arm and the floor:

| Pose | J1 angles that touch something |
|---|---|
| rest | −105° … −25° |
| reach out | −100° … −25° |
| reach low | −155° … −20° |

Today's J1 range is −89° … +89°, so **−89° … −25° (64°) is unusable**. Turning
the mount outward by φ moves the range to φ − 89 … φ + 89:

| Turned outward by | Usable arc | Straight ahead / both hands meet in front (−18°) | Reach behind |
|---|---|---|---|
| 0° (today) | about 114° | ✅ / ✅ | to +89° (sideways) |
| **60–70°** | **about 170–178°** | ✅ / ✅ (just) | to +149…159° |
| 90° | 178° | ✅ (at −1°) / ❌ | to +179° (straight back) |

**Recommendation:**
- **About 70° outward** keeps both hands meeting in front and still gives almost the whole outer half.
- **90°** is better only if reaching straight behind matters more than two-handed work in front.

**What changes either way:**
- The arm base's J1 housing turns by the same angle; check it on the arm-base disc and the cable exit.
- J1 has to be recalibrated, and its EEPROM range redone.
- The rest pose stays the same shape, at J1 = −φ.

## Done: 70° outward

**What changed in Fusion:**
- **`Arm base (merged, concept)`:**
  - Only the J1 housings turn 70° about J1, inside the base feature, so the later joins re-run on the turned housings.
  - The pedestal and its 4 bolts stay on the motor bracket.
  - Each housing now sits on the inner side of J1 (±110° from forward), at most 49.6 mm from the axis. That is inside the 2nd floor's R76 notch.
  - It overhangs the Ø90 disc by about 8 mm, so a 46 × 43 × 8 support lobe under each housing carries it.
  - Clash check against the plates, posts, covers and IBT-2s: 0 mm³.
- **Preview drawing:**
  - The ElRobot arms are still drawn facing front, as the user asked. In the design, J1 = −70° brings the hands forward.
  - The STEP's own table base and shield are hidden; gerdoo's arm base replaces them.
  - The J1 servo in the STEP is drawn unturned. The real one sits in the turned housing.

**Simulator:**
- Each mount has yaw −90° ± 70° about J1, and J1 stays on its axis at (0, ±145.7).
- Presets: rest is J1 = −70° (left) and +70° (right).
- The sweep now shows **no contact anywhere in J1's ±89° range** for rest, reach and reach low. Hands still meet in front without touching.

**On the robot:**
- Turn each J1 housing 70° outward on its base.
- Recalibrate J1. The panel's Calibrate… writes the new offset.
- Redo J1's `RANGE`.
- Check that J1's servo cable reaches with the housing turned.

## Also applied

- **USB hub:** pilots on the vendor's **58 × 49**. The user's 50.2 was a measuring slip.
- **Dock plates:** 1.5 mm thick. The pockets were rebuilt so the plate faces stay at z −129.85; the first attempt had lost its target body.
- **Light dial:** there is no potentiometer. The light is driven by the AOICRIE dual-MOSFET module (D4184, 15 A, 5–36 V, PWM 0–20 kHz), which already sits on the base. The back cover's dial hole is closed; the boss stays as a blank medallion.

## The dock: plate fixing and the light

**Fitting the contact plates.** No soldering; all access is from the dock's open underside.

1. **Drill each 34.2 × 43.7 × 1.5 plate:** two Ø3.2 holes on the plate's centre line, 3.5 mm in from the top and bottom edges. Countersink them on the copper side.
2. **Lower hole:** fit a countersunk **M3 × 10** through the plate and the wall into the dock's hollow. Inside, put the wire's **ring terminal**, a washer and a nut in the Ø9 spot-face. That one screw holds the plate and carries the current.
3. **Upper hole:** fit a countersunk **M3 self-tap** into the Ø2.5 pilot.
4. **Wiring:** dock DC jack + → presence microswitch (COM → NO) → right plate; DC jack − → left plate. Pick one polarity and match the robot's pins to it.

The plate's copper face ends up at z −129.85, with the pins compressing by about 1.5 mm when they protrude 5–5.5 mm.

**Ambient light.**

*The sign head is a light box:*
- **Box:** a 208 × 30 × 48 hollow behind "GERDOO", open at the back.
- **Wall wash:** an LED strip on the inner front wall, facing backwards, lights the wall behind the dock.
- **Light line:** a 190 × 2.5 slot under the letters glows forwards through a printed diffuser strip (white or translucent PLA, `light line diffuser`).
- **What stays solid:** the 3 mm front wall behind the letters, and the lidar V and ribs below.
- **Wire route:** an 8 × 4 groove down the back of the head and the mast, then along the mast foot and through a Ø8 hole into the cradle's hollow.

*Controller, in the cradle hollow* (`dock/dock_light/dock_light.ino`; compiles for the Nano: 5 KB of 30 KB):

| Part | Source |
|---|---|
| Arduino Nano (or any 5 V Arduino) | the old Nano build |
| **XL4015 set to 5.0 V** from the 19 V input | the spare. Set it with a meter **before** connecting anything. The MINI560s stop at 20 V, too close to a 19.5 V charger |
| WS2812B strip, 5 V, 60/m, 18 LEDs (30 cm) | buy |
| 330 Ω in the data line, 1000 µF across the strip | buy / parts bin |
| 100 k + 33 k divider from the plate + line to A0 | parts bin |

*How it tells home from away:* the plate line only carries 19 V while the robot holds the presence switch closed. So the same switch that makes the plates live also tells the Nano that Gerdoo is home.

*Behaviour:*
- **Home:** green sweeps out from the middle, then settles to a barely-breathing glow.
- **Away:** slow amber breathing.

*Current:* about 0.4 A at most, at brightness 140/255.

*In the simulator:* the dock glows green while the robot is docked and amber while it's away. The room's back wall moves up behind the dock so the glow shows on it.


## Still open

- **"Left side" of the dock:** taken as seen facing the dock. It's a mirror if that's wrong.
- **Pogo pin spring travel.**
