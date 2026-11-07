# 044 — Base-board holders v2: screwed walls beside the battery, a smaller servo tower

| | |
|---|---|
| **Date** | 2026-10-22 |
| **Type** | Redesign after a test print |
| **Status** | ✅ In `gerdoo-assembly-preview` v40, clash-checked · ✅ `gerdoo_base_board_holders_v2_A1.3mf`: 3 h 22 min, 60.3 g PLA + 0.3 g PETG, 2 swaps · ⏳ Not printed |
| **Severity** | Medium: v1 printed but wasn't usable |

---

Replaces [043](043-2026-10-21-base-board-holders.md).

## Why v1 failed (the user printed it)

**The user's points:**
- **Everything must be screwed.** The rings, snap latches and zip ties of v1 rattle as the robot moves, and they aren't safe.

**The user's new layout:**
- **Side walls:** a ~3 mm wall on each side of the battery, **12 mm out from the battery holder's side** (measured from the holder, not its screws), from the deck to about 20 mm under the 2nd floor.
- **On the walls:** both power boards (one per side), the MOSFET board, the voltage sensor and both converters.
- **Servo board:** keep its place and its screws, but on a smaller tower **screwed together with the Teensy board**.
- **Spare screw points** on the walls for future boards.

## Measured by the user

| Board | Measurement | Fixing used |
|---|---|---|
| Power board PCB007 | holes **90.7** apart, on the centre line (board 95 × 18.7) | M3 inserts, 3.5 mm standoffs |
| D4184 MOSFET | **13.2** (read as the spacing of its two holes at the PWM end; a hole is visible in that corner) | M2 inserts, 4 mm standoffs; a pad under the other end |
| XL4015 charger | **47.4 × 21.4** (read as hole centres; the photos make the board about 51 × 26) | 4 × M3 inserts, 5 mm standoffs |
| Voltage sensor | one **M3** hole | M3 insert at its centre, 2 support pads |
| MINI560 | no holes | snug pocket (29 × 18 from the listing), rails top and bottom, open at both ends for wires; glue if needed |

## The parts (preview coordinates)

### Side walls ×2
- **The wall:** 3 mm thick at x ±63.8…66.8, so its inner face is 12 mm from the battery's side (listing size x ±51.8). It runs z −79…22 (just in front of the rear hex post to just behind the motor driver) and is **58 mm tall**, 19 mm under the 2nd floor. Vertical.
- **Front end:** a 1.6 mm frame under the motor driver's 4 standoffs, clamped by their screws. The driver sits 1.6 mm higher; use screws 2 mm longer.
- **Inner flange (toward the battery):** 7 × 2.5 mm, with **2 × Ø3.4 holes** at z −68 and −40. **Drill through the deck** using them as a guide, then M3×16 with a nut underneath. Under the deck there they are clear of the ultrasonic pods (z ≤ −76) and the drive motors (|z| ≤ 18).
- **Boards on the outer face:**
  - **Both walls:** the power board along the bottom. Its bottom edge is at y 8, because the arm base's foot reaches in to x 79.5 below y ~8 near the drive. Above that the arm base is beyond x 85.5, and the terminals end at x 81.9.
  - **Robot-left (+x):**
    - MINI560 pocket and D4184 above the power board;
    - spare **M3 insert bosses**: 5 along the top (y 54.3, z −70…10) and 1 at (37, 10).
  - **Robot-right (−x):**
    - XL4015 above the power board, its bosses 0.5 mm clear of the board's top edge;
    - voltage sensor;
    - spare bosses at (54.3, ±10) and (38, 16).

### Servo tower
- **Size:** a 46 × 42 × 2.5 mm wall in front of the Teensy board, with a flange along its foot.
- **Teensy fixing:** two 1.2 mm **ears** reach under the Teensy board's front corners, and **its own M2 screws** clamp them.
- **Servo board:** 4 bosses with M2 inserts on Waveshare's 37 × 28.
- **Washers:** two printed **1.2 mm washers** go under the Teensy board's back corners to keep it level.

### Checks
- **Clash check against the preview:** the only overlaps are the planned ones (the frame under the driver standoffs, the ears and washers under the Teensy board).
- **Fixed during the check:**
  - the power board terminals ran into the arm base's foot (147 mm³), so the board moved up and closer to the wall;
  - the charger bosses touched the power board's edge by 0.94 mm³, so the charger moved up 0.5.

## Print file

**`~/Downloads/gerdoo_base_board_holders_v2_A1.3mf`** (spec `sim/web/tools/plate_base_board_holders.json`):
- **Orientation:** walls standing, tower standing, washers flat.
- **Supports:** only under the tower's two ears, by enforcer, with a 2-layer PETG interface (2 swaps), plus a 35 mm prime tower.
- **Slice:** 3 h 22 min, 60.3 g PLA, 0.3 g PETG.
- **Why the enforcers reach Z 7:** at Z 0–6 they stopped exactly at the ears' underside, and Bambu generated no support at all.

## Hardware

| Where | What |
|---|---|
| Walls to the deck | 4 × M3×16, nuts and washers (drill 4 × Ø3.4) |
| Motor drivers | 8 standoff screws, 2 mm longer |
| Power boards | 4 × M3 inserts, 4 × M3×8 |
| Charger | 4 × M3 inserts, 4 × M3×10 |
| Voltage sensor | 1 × M3 insert, 1 × M3×10 |
| D4184 | 2 × M2 inserts, 2 × M2×8 |
| Servo board | 4 × M2 inserts, 4 × M2×6 + washers (its holes are M2.5) |
| Teensy board | its 4 M2 screws, 2 mm longer |
| Spare points | 9 × M3 inserts, when needed |

## Assumed

- **Battery side:** at x ±51.8 (listing). If the real holder is wider, the 12 mm gap shrinks by the same amount.
- **D4184:** the 13.2 is its hole spacing at the PWM end.
- **MINI560:** 29 × 18.

## v3: power boards on top, boards toward the tail (the user asked)

**The user's points:**
- The power board has the most screws and will get more wires, so it goes at the **top** of each wall, where it's easiest to reach.
- The boards fitted now go **toward the tail**: easier to install, and the user doesn't mind if future boards are harder to reach.

**Changes:**
- **Power board:** now at y 38.5…57.2 (holes at y 47.85), still 3.5 mm off the wall.
  - **Up top:** the arm base's top disc is beyond x 90, and the terminals end at x 81.9.
  - **Top-row wires:** 20 mm of room before the 2nd floor.
- **Below it, packed against the back end:**
  - **Robot-left (+x):** the MINI560 pocket at z −77…−47.7, then the D4184 (holes at z −15.1).
  - **Robot-right (−x):** the XL4015 at z −74.5…−22.5, then the voltage sensor at z −21…6 (screw at z −7.5).
- **Spare M3 points:** all moved to the front end: robot-left (y 15/31, z −2/18), robot-right (31, −2), (31, 18), (15, 18).
- **Clash check:** clean.
- **Plate:** `~/Downloads/gerdoo_base_board_holders_v3_A1.3mf`, 3 h 21 min, 60.3 g PLA + 0.3 g PETG, 2 swaps. The v2 file is removed.
- **Preview:** saved as v41.

## v4: anchored on the battery screws, an extension grid, no overhangs

**The user's catch:** the walls stand next to the battery, so they should hang off the **battery holder's screws**, not the motor drivers' standoffs. The holders are already screwed to the deck's 4 M4 holes, and nothing electrical is clamped there.

**Anchoring:**
- Each wall now has two 1.6 mm **tabs under the battery holder's M4 screws** on its side:
  - front: (±36.5, −25), inside the wall's length;
  - back: (±36.5, −106.7), reached by a tab that turns inward at z −73 and runs under the battery, clear of the rear hex post.
- **Removed:** the motor-driver frame and the 2 deck-drill holes. **No drilling.** The drivers stay as they were.
- The battery stack sits 1.6 mm higher, evenly on all 4 corners. Use M4 screws 2 mm longer.
- **Clash check:** the only overlaps are the planned tabs under the battery holder (placeholder) and its copper posts.

**Future boards (the user said I'd skipped this):**
- **Extension grid:** M3 through-holes (Ø3.4) on a 20 mm pitch, rows y 7 / 27 / 47 and columns z −70…10, the 3rd floor's pitch. A hole is kept wherever the wall around it is plain:
  - **robot-left:** 8 holes, at (7, −30), (7, −10), (7, 10), (27, −30), (27, 10), (47, −50), (47, −30), (47, −10);
  - **robot-right:** 9 holes, at (7, −50), (7, −10), (7, 10), (27, −50), (27, −10), (27, 10), (47, −50), (47, −30), (47, −10).
- Through-holes work from **either face**: outside, or in the 12 mm gap toward the battery for flat boards. Use M3 screws and nuts.
- **Spare M3 insert bosses** stay at the front end: 4 robot-left, 3 robot-right.

**Printing (the user asked whether supports are needed):**
- **45° chins under every horizontal boss and pad.**
- The 5 V converter pocket's top rail is cut to 2 mm deep.
- **Floating check:** only the insert holes' tops are left, bridges of 4.4 mm or less. The only supports are still the two servo-tower ears (PETG interface).

**Files:**
- **Plate:** `~/Downloads/gerdoo_base_board_holders_v4_A1.3mf`, 3 h 20 min, 58.6 g PLA + 0.3 g PETG, 2 swaps. v3 is removed.
- **Work files:** now in the repo's git-ignored `build/print/`, since the session scratch folder is gone.
- **Preview:** saved.

## v5: stronger bottom connections (the user saw weak points)

| Joint | v4 | v5 |
|---|---|---|
| Battery-screw tabs | 1.6 mm thick, 6–8 mm wide, Ø10 rings, a step where they met the 2.5 mm flange | **3 mm thick, 12 mm wide, Ø13 rings**, one flat plane with the flanges |
| Inner flange (battery side) | 2.5 × 7 mm | **3 × 7 mm** |
| Outer flange | none | **3 × 5 mm**, the full length |
| Wall-to-flange joint | a bare right angle | **5 gussets inside** (10 mm tall, between the grid-hole columns) and **4 small ones outside** (5 mm) |
| Back tab route | 6–7 mm wide | **12 mm wide**: inward at z −78…−66, then back along x 38…50. It stays 1 mm clear of the rear ultrasonic-lead slot and clear of the rear hex post |
| Servo-tower ears | 1.2 mm thick, meeting the wall over only 0.2 mm | **2 mm thick**, running all the way into the wall, plus a rib above each one beside the Teensy board's edge |
| Teensy washers | 1.2 mm | 2 mm |

**Knock-on effects:**
- The battery stack sits **3 mm** higher (M4 screws 3 mm longer).
- The Teensy board sits **2 mm** higher (M2 screws 2 mm longer).
- **Clash check:** only the planned overlaps (the tabs under the battery and its posts, the ears and washers under the Teensy board).

**Plate:**
- `~/Downloads/gerdoo_base_board_holders_v5_A1.3mf`: **3 h 57 min, 67.2 g PLA + 0.3 g PETG**, 2 swaps, no warnings.
- v4 removed.
