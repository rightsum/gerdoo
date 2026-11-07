# 039 — 3rd floor: a slot for the head cables, a unified extension grid, ready to print

| | |
|---|---|
| **Date** | 2026-10-20 |
| **Type** | Design change + print setup |
| **Status** | ✅ `3rd-floor-v2` edited, all walls ≥ 2 mm · ✅ `gerdoo_3rd_floor_A1.3mf` v3 (floor + cap + antenna bracket, no supports) slices cleanly · ⚠️ `3rd-floor-v2` not saved yet (the API save left it modified at v3; Cmd+S) · ⏳ Not printed |
| **Severity** | Medium: without this, the head cables had no way down |

---

Follows [038](038-2026-10-19-printing-the-2nd-floor.md), [035](035-2026-10-17-sts3215-neck-and-taller-lidar.md) (neck) and [030](030-2026-10-16-front-and-back-covers-and-the-cable-plan.md) (cable plan).

## What the user asked

1. **A slot for the head cables.** The head cables are a USB (power) and an HDMI. The user wanted "a line of space" between the vent and the neck servos, down to the 2nd floor, so the cables can move with the neck.
2. **Move the lidar cable slot a bit** so it doesn't merge with the extension holes.
3. **The old pillar recess between the vent and the servos isn't needed.** No pillar stands there any more.
4. **Extension holes:** some were already there, but unify them into one grid.

## Findings

- **No through-path for the head cables existed.** Log 030's cable plan sends the screen HDMI + USB, the Brio and the neck servos through a "Ø17 hole, front". In the model it's **a Ø17 × 3 mm recess in the underside**, for an old pillar between the 2nd and 3rd floor. The neck's pan base (log 035) routes its servo cable to that spot.
- **The lidar cable slot** (14 × 9, behind the mast) was 0.2 mm from an old grid hole.
- **Two old extension grids didn't line up:**
  - Ø3.5 × 5 at 20 mm pitch, offset 9.6 mm;
  - Ø3.5 × 7 at 20 mm pitch on a different offset;
  - plus a 38 mm square of Ø3.4.
- **Several grid holes broke into the speaker chamber and grille.**

## Changes (`3rd-floor-v2`, floor-local coordinates; world = (−x, −z))

| Change | Detail |
|---|---|
| **Head cable slot** | **60 × 14 stadium** at world (0, +46), from the vent to the pan base, cut through to the 2nd floor. It passes the screen's HDMI + USB plugs, the Brio USB, the pan-servo cable, and a 40-pin IDC plug (56 × 9) for the spare GPIO ribbon (log 035). The pan base's cable channel ends at it. **Walls:** 2.1 mm to the nearest vent hole, 3.8 mm to the neck inserts, 2.5 mm to the pan base. |
| **Lidar cable slot** | Moved **3.5 mm back**, to world z −39.5, by moving its sketch. It is now 7 mm from the holder plate's edge and 6 mm from the speaker frame. |
| **Old pillar recess** | Filled (Ø17 × 3). |
| **Old grids** | Suppressed: Hole12/R-Pattern4, Hole13/R-Pattern5, Hole14/R-Pattern6. |
| **Notch fillets** | The old `notch corners` fillet was built on edges of the grid holes. Suppressing the grids suppressed it too, and un-suppressing it brought the grids back. It stays suppressed, and a new **r6 fillet on the 4 real notch corners** was added at the end. Same geometry as before. |
| **Extension grid** | **22 × Ø4.4 through-holes** (M3 heat-set insert, the panel standard) on **one 20 mm grid centred on the floor**, mirror-symmetric: x ±40 for z −100…+100 (except z 0, where the arm notches leave the floor only ±45.7 wide), plus 2 at (±20, 40) beside the lidar slot. |

**How the extension grid was placed:** it skips points within the margins around:
- the edge and notches (7 mm);
- the lidar holder plate;
- the vent;
- both slots;
- the pan base;
- the speaker frame;
- the corner posts;
- the back hole;
- the front cover's radial inserts.

The other lattice offsets were checked too. The centred one was the only mirror-symmetric choice with this many holes.

**Unchanged:** the user's vent cluster, the lidar holder's centre bolt, the speaker inserts, chamber, grille and cap, the corner post holes, the neck inserts, and the cover inserts. The early `Sketch6` warning ("project source lost, cache used") was already there.

## Speaker space (the user asked)

| Direction | Clearance |
|---|---|
| Sideways to the Jetson | 4.7 mm (the frame spans world z −50…−100; the Jetson ends at −45.2) |
| Grille cap | 7 mm |
| Below, to the USB hub | ~28 mm. The model assumes a speaker depth of 18 mm, so up to ~45 mm fits. |

## Print file

**Orientation:** the floor prints as mounted.

**Overhangs below 40°:**
- the speaker chamber's perforated ceiling, 46 mm across at 8 mm, 978 mm²;
- the ceilings of the speaker insert holes, 63 mm², bridged.

**Supports:**
- **under the chamber only** (enforced), normal grid supports with a 2-layer PETG interface;
- **prime tower:** 35 mm, no ribs, in the left notch pocket at (15, 110).

These follow the rules from logs 033 and 036.

**Grille cap:** printed top-down in the right notch pocket, with no overhangs.

**Slice (Bambu Studio 2.8 CLI):** 8 h 47 min, 162.3 g PLA + 1.5 g PETG, 2 filament changes, no warnings.

**Files:**
- `~/Downloads/gerdoo_3rd_floor_A1.3mf`;
- spec `sim/web/tools/plate_3rd_floor.json`.

## Still open

- **Arm elbows against the 3rd floor's R100 notches.** Log 029 left this open, before the J1 mounts turned 70° outward. The fallback is a firmware limit on the elbow near the floor, which doesn't change this print.
- **Measure the real speaker depth.**

## One speaker grille, not two (the user's call)

**The question:** the user asked why the speaker has two grilles. Log 030's design was a perforated 2 mm floor skin plus the honeycomb cap, offset by half a cell over a 2 mm gap, so nothing could drop straight onto the cone.

**What was wrong with that:**
- **Sound:** two offset grilles with an air gap cut the open area and muffle the treble, which is what makes speech clear.
- **Printing:** the skin was a 46 mm perforated ceiling, the plate's only overhang. It alone forced the supports, PETG and prime tower.

**Change:**
- The floor's grille feature is suppressed, and the speaker gets a **Ø46 opening straight through**.
- **The cap is now the only grille.** Its 3 pins sit in their Ø3.1 holes outside the opening, with 1.45 mm of wall.
- The 4 speaker inserts underneath are unchanged.

**Plate v2:** PLA only, no supports, no prime tower. 8 h 14 min, 158.5 g, no filament changes, no warnings. The remaining overhangs are the insert-hole ceilings (Ø4.4) at 7 mm, which bridge.

## The antenna bracket joins this plate

**Placement:** the one-piece bracket from log 038 (146 × 53) nests in the left arm-notch pocket.
- Its outer curve faces the bed edge, and its arms point at the floor.
- Map `z,x,y` (a proper rotation, not a mirror), at (30, 128).
- It sits at X 3.5–56.5, Y 54.8–201.2, 10.7 mm from the floor.

**Result:** the separate antenna file is no longer needed.

## The Jetson vent: a honeycomb ring (the user asked)

**The request:** make the user's old vent (Ø3 holes: a ring of 14 plus a 5 × 5 grid, in front of the mast) look like the speaker grille, but with small holes.

**A check first:** `lidar-holder-v2` stands on its **Ø24 post only** (402 mm² on the floor). Its 55.6 mm square plate is at the top, under the C1. So the floor around the post is open to the air.

**Change:**
- The old vent features (Hole9, C-Pattern1, Hole10, R-Pattern2) are suppressed. Nothing else depended on them.
- New vent: a **honeycomb ring around the mast**, r 14–26.5, of **168 hex cells**, 2.0 mm across the flats with 1.0 mm ribs (3.0 pitch). The cells are too small for M2 or M3 screws to fall through.
- The ring is centred over the Jetson, and the warm air rises around the mast.
- The post's Ø24 seat (r 12) and the centre insert stay solid.

## Light and temperature sensors (the user asked where)

Both go on this floor, at the **back corners**, on the extension grid.

**Why not the front:** the screen's glow and the head's shadow would fool the LDR, and the screen board would warm the temperature sensor.

| Sensor | Where (world) | Why |
|---|---|---|
| Keyestudio LDR | back-right, on grid hole (−40, −100), facing up | Clear view of the ceiling. The head and mast are in front of it. |
| DHT22 | back-left, on grid hole (40, −100) | About 100 mm from the vent's warm air and clear of the speaker. Open air: the back cover stops below the 2nd floor. |

**Mounting:** each sensor fastens with an M3 screw into an insert in its grid hole. The DHT22's tab hole is Ø3.

**Wiring:**
- A **12 × 4 wire slot** beside each sensor at (±40, −90) passes a 4-pin DuPont plug.
- The wires drop right beside the hub to the 2nd floor's T3 passages, then on to the Teensy (LDR on A1, as now).

**Clearances:** ≥ 5.8 mm to the grid holes, ≥ 11 mm to the corner posts, 6 mm to the 2nd→3rd posts below.

## Plate v3

**Parts:**
- 3rd floor (vent ring, sensor slots, one speaker grille);
- grille cap;
- antenna bracket.

**Slice:** PLA only, no supports. 9 h 38 min, 176.5 g, no filament changes, no warnings.

## Antenna bracket v2: oval arms (the user asked)

**The request:** the arms were too big and ugly. The user wanted them oval and only as long as needed, to the hole.

**What they were:** 36 × 30 mm rectangles reaching 16 mm past the bolt hole, to where the old pins were.

**`antenna-bracket-back-v1`, new geometry:**
- Each arm is now a **12 mm wide oval tab**, radial at ±15°.
- It runs from r 104 to r 127. The round end has a 6 mm radius around the Ø4.4 bolt hole at r 110.
- **3 mm fillets** where it meets the band.
- Same 3 mm thickness, so the hub's 5 mm spacer still lands at 8 mm. The arm fully surrounds the spacer's footprint.
- The band and the SMA holes are unchanged.

**Result:** 18.4 → 14.4 cm³; one solid; no collisions in the preview, which now shows v2.

**3rd-floor plate:** the bracket now takes X 4–44 in the left pocket, 10.3 mm from the floor. 9 h 30 min, 172.6 g, no supports, no warnings.

## Sensor mounts, sized from the user's measurements

**Measured by the user:**
- DHT22 module (red AM2302 board): **38.9 × 22.1**.
- Keyestudio LDR: **29.8** long, 20.1 wide by photo ratio. That matches Keyestudio's 30 × 20 spec with a Ø3.2 hole.

**Estimated from the photo:** the LDR hole centre is about 11.3 mm from the header edge, centred across the width.

**No spot on the floor's back half avoids the extension grid.** A search with 2 mm margins found none. So each sensor gets a **printed mount screwed into two grid holes**. That's what the grid is for.

**New design `sensor-mounts-v1`, preview frame.** Both are copied into the preview's fit study, and neither collides with anything.

| Mount | Where (world) | Design |
|---|---|---|
| **LDR cradle** | back right; grid holes (−40, −80) and (−40, −100) | Pocket **30.1 × 20.4**, open at the header end so the board slides in. Solder relief under the board, open at the header end. **M2 boss + insert (Ø3.2 × 4)** at the board hole, so the M2 has ±0.6 mm of slack in the board's Ø3.2 hole. The 2 × M3 socket heads sit in counterbores inside the relief, under the board. 24.4 × 32.1 × 6.0. 1 mm clear of the speaker cap. |
| **DHT22 rail mount** | back left; grid holes (40, −80) and (40, −100) | Base 25.4 × 32 × 5. **Two rails, 22 mm tall, with 1.9 × 2.5 grooves** for the board edges, with lead-in notches. The board stands with its grille facing back, and the white housing clears the rail lips by 1.15 mm. The header points down through a 12 × 4 slot in the base, over the floor slot, so the DuPont plug fits from below. 2 × M3 counterbored. 1.3 mm clear of the speaker cap. |

**Floor wire slots, redone:**
- The old pair is suppressed.
- **DHT22:** at world (42, −90), under its mount, lined up with the pin row 2.2 mm in front of the board.
- **LDR:** at world (−41, −53), where its DuPont plugs end in front of the cradle.

**Hardware:**
- **LDR:** 2 × M3 inserts in the grid, 2 × M3×6 or M3×8 socket caps, 1 × M2 insert, 1 × M2×5.
- **DHT22:** 2 × M3 inserts, 2 × M3×8.

**Printing:** neither mount has overhangs. They sit beside the grille cap in the right notch pocket.

**Plate:**
- **Parts:** floor, grille cap, antenna bracket, both mounts.
- **Slice:** 10 h 7 min, 179.9 g PLA, no supports, no warnings.
- **The first layout failed:** the slicer reported a toolpath conflict, because the LDR cradle sat 0.9 mm from the floor.

## LDR cradle v2: a cable path built into the mount (the user's catch)

**The problem:** the Keyestudio's right-angle header sits at the front end of the board, next to the screw hole. Its DuPont plugs stuck out of the cradle's open end, and the floor slot sat loose 20 mm further on. The DHT22 mount has its pin slot built in; the LDR mount had nothing.

**Change (`sensor-mounts-v1`):**
- The cradle now continues as a **26 mm cable tray** in front of the header end (base 2.4 mm, low side walls).
- A **12 × 4 slot at the plug tails**, world (−41, −53), runs through the tray and lines up with the floor slot. The plugs lie in the tray, and the wires go straight down to the 2nd floor and on to its T3 passage.
- New size: 24.4 × 58.5 × 6.0. No collisions in the preview.

**Plate:**
- Re-packed with a clearance search on densified outlines, 5 mm minimum. The first packing checked only mesh vertices and missed the cradle's long straight edges against the notch arc, so the slicer flagged a toolpath conflict.
- Positions: grille cap (209, 113), LDR cradle (230, 176), DHT22 mount (233, 20).
- **Slice:** 10 h 12 min, 181.7 g PLA, no supports, no warnings.

## LDR cradle v3: pins bent down, compact (the user's call)

**The problem:** the cable tray made the mount 58.5 mm long for a 30 mm board. The root cause is the right-angle header, whose DuPont plugs stick out sideways about 16 mm.

**Decision (the user):** bend the 3 header pins 90° down, about 2 mm past the board edge.

**Cradle v3 (`sensor-mounts-v1`):**
- Same pocket, relief, M2 board screw and 2 × M3 into the grid.
- A **12 × 4 slot 2 mm past the board's header edge**, at world (−41.2, −73.55), through the cradle and the floor. The board drops in from above with its bent pins in the slot, and the DuPont plug fits from below, as on the DHT22.
- **Size:** 24.4 × 37.5 × 6.0 (was 58.5 long).
- **Collisions:** none.

**Floor:**
- `sensor wire slots v3` replaces v2.
- Both sensor slots now sit under their mounts:
  - DHT22 at (42, −90);
  - LDR at (−41.2, −73.55), 2.3 mm from the grid hole at (−40, −80).

**Plate:**
- Re-packed by `pack_plate.py`, 5 mm minimum clearance on densified outlines.
- Positions: cap (208, 118), LDR cradle (16, 22), DHT22 mount (16, 223).
- **Slice:** 10 h 7 min, 180.5 g, no supports, no warnings.

## The grid standard: pass-throughs instead of per-sensor slots (the user's call)

**The problem:** the floor had custom wire slots for exactly these two sensors in exactly these spots. A new board would need another custom cut.

**The standard:**
1. **Mounting:** the M3 extension grid, 20 mm pitch.
2. **Cables:** **Ø11 pass-throughs**, each midway between two neighbouring grid holes.
   - A 4-pin DuPont plug fits through in any orientation.
   - 2.3 mm wall to each grid hole.
3. **Adapters:** every board gets a printed adapter that screws into **two neighbouring grid holes**, with its connector over the pass-through between them.

**Floor:**
- First version: 18 pass-throughs (every midpoint). The user found it too busy.
- Now **8**, at world x ±40, z ±50 and ±90, one per group of grid holes, front and back on each column.
- The custom `sensor wire slots v3` is suppressed.
- Closest wall: 2.3 mm to a grid hole.

**Sensor adapters (`sensor-mounts-v1`):**

| Adapter | Grid holes | Pass-through | Notes |
|---|---|---|---|
| DHT22 rail mount v2 | (40, −80), (40, −100) | (40, −90) | Ø11 window in the base under the pin row. The base is trimmed on the speaker side; the inner rail post clears the grille cap by 1.1 mm. |
| LDR cradle v6 | (−40, −80), (−40, −60) | (−40, −90) | Mirror of the DHT22 spot. Header toward the back, pins bent down into the window. **2 × M3 under the board** (heads in the relief, fitted before the board). The board is held by **4 press-fit ribs (0.25 mm)**. No M2: the board's hole sits 3.3 mm from a grid hole. **Flat bottom:** an earlier locating peg made the slicer flag the part as floating. |

**Collisions:** none for either adapter.

**Plate:**
- **Parts:** floor, grille cap, antenna bracket, both adapters.
- **Slice:** 10 h 12 min, 179.2 g, no supports, no warnings.

## Is the mast stable with the vent ring? (the user asked)

**Load on the mast:**
- C1 about 110 g plus holder about 55 g, combined centre of mass about 137 mm above the floor.
- Braking at 0.5 g gives about **0.11 N·m** at the foot; a hard 2 g knock about 0.44 N·m.

**Tipping:**
- The Ø24 foot clamped by one M3 holds roughly 300–500 N × 12 mm, about **4–6 N·m**. That's 10–50 times the load.
- The vent ring starts 2 mm outside the foot (r 14 vs r 12). It's 56 % solid honeycomb, 10 mm deep, so the loads through it are negligible.

**The real weak spot is yaw.** One central bolt resists turning only by friction, about 1 N·m. A knock could turn the mast and shift the lidar's zero heading, which matters for mapping.

**Proposed fix:** a second M3 at world (0, 7), inside the foot.
- Ø3.4 through the floor's solid inner disc.
- Ø4.4 × 7 insert in the post foot, with a 2.6 mm wall to the centre insert.
- `lidar-holder-v2` isn't printed yet, so this costs nothing.
- **Status:** waiting for the user.

## Fusion closed; both floors rebuilt from the logs

**What was lost:** Fusion's documents were all closed, and `3rd-floor-v2` was back at **v3** and `2nd-floor-v2` at **v9**. None of the floor edits since 2026-10-19 had reached the cloud.
- The API's `save()` and the MCP save both reported success, but no version was created.
- At the time, the preview had opened second, background copies of both floors.

**What survived:** `sensor-mounts-v1` v2, `antenna-bracket-back-v1` v2 and the preview v33 had saved. The print files were already exported.

**Rebuilt by script**, with the logged parameters:
- **`2nd-floor-v2` → v10:**
  - sound-board bosses;
  - pin pockets filled, front and back centre holes plugged;
  - hub moved and switched to M2 (bosses, shared inserts);
  - 2 spacer bodies.
  - **Volume 349.75 cm³, identical to the lost version.**
- **`3rd-floor-v2` → v4:**
  - old grids and old vent suppressed, pillar recess filled;
  - lidar slot moved, head cable slot, 22-hole extension grid, r6 notch fillets;
  - Ø46 speaker opening;
  - the 8 Ø11 pass-throughs;
  - **plus the bigger honeycombs below.**
- **The saves that worked this time:** the MCP save on the copy opened in the foreground. The version number was checked after each upload.
- **The preview's references** were updated to these versions and saved.

## Honeycombs made printable (the user's report)

**The problem:** the speaker cap's cells (3.2 with 0.8 ribs) and the Jetson vent's cells (2.0 with 1.0 ribs) were too fine, and the printer messed them up. The cap prints face-down, so its cells are in the first layer, where squish and elephant-foot compensation close thin ribs.

| | Before | Now |
|---|---|---|
| Jetson vent ring (r 14–26.5, 10 mm deep) | 168 hex, 2.0 across flats, 1.0 ribs | **66 hex, 3.0 across flats, 1.2 ribs** (pitch 4.2) |
| Speaker cap top (1.6 mm, cells within r 23.5) | 97 hex, 3.2 / 0.8 | **55 hex, 4.2 / 1.3** (pitch 5.5); open area 43 %, about the same as before |

**How the cap was rebuilt:** its top had been one join (the outer circle minus the cells). That feature is suppressed, and a new top is built on a plane at y 12.

**Plate:**
- **Parts:** floor, grille cap, antenna bracket, both adapters.
- **Slice:** 9 h 49 min, 177.9 g, no supports, no warnings.
