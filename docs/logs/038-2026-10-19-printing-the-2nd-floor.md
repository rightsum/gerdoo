# 038 — The 2nd floor is ready to print: sound-board mounts, the hub on the antenna bolts, PLA only

| | |
|---|---|
| **Date** | 2026-10-19 |
| **Type** | Print setup |
| **Status** | ✅ Sound-board mounts added; hub shares the antenna bolts · ✅ Collision-checked · ✅ `gerdoo_2nd_floor_A1.3mf` v5 (floor + 2nd→3rd separators) slices cleanly · ✅ Antenna brackets joined into one piece · ⚠️ Not saved yet: `2nd-floor-v2` (the API save left it modified at v9), `antenna-bracket-back-v1` (saveAs pending) and the preview. Cmd+S each, in that order · ⏳ Not printed |
| **Severity** | Low |

---

Follows [036](036-2026-10-18-arm-bases-and-separators-print.md) (the 1st→2nd separators) and [033](033-2026-10-17-printing-the-1st-layer-on-the-a1.md) (printing rules).

## Why the 2nd floor next

**What it unlocks:** it's the next plate in the stack. The 1st→2nd separators on the arm-base plate (log 036) carry it, and the 2nd→3rd posts use the same corners.

**My first answer was wrong:** I suggested the neck first, because log 029 lists "post holes 5 mm off" as open. In fact `2nd-floor-v2` (version 9) already fixed it:
- features 31–34 plug the old corner holes and re-cut them **aligned with `1st-layer-v4`** at (−65, ±90) and (60, ±90);
- the floor is linked in the assembly preview, at y 77–87.

**Already in v9:**
- R76 arm notches;
- old side slots filled;
- antenna bracket holes and pin pockets;
- cable trunks T1L/T1R and T3L/T3R;
- USB hub pilots (Ø2.1 for M2.5 standoffs, vendor's 58 × 49);
- mic-ring FPC channel;
- 4 radial cover inserts;
- Ø17 × 3 recesses underneath for the round posts.

Both unhealthy features (Sweep1, Fillet3) are suppressed.

**Doesn't depend on the 3rd floor:** the 3rd floor's open question (narrow at the arms, log 029) doesn't touch the 2nd floor. The posts between them stand on the same corner holes.

## Printability

**Orientation:** as mounted, underside on the bed. The footprint is 210 × 250 mm, a R125 disc with flats and arm notches.

**Overhangs below 40°**, measured on the exported STL:

| Height | Area | What | Action |
|---|---|---|---|
| 0.2–0.7 mm | ~600 mm² | the 2 mm fillet on the bottom edges | none, first layers |
| 3 mm | 452 mm² | the two Ø17 recess ceilings | bridged, 17 mm |
| 6–7 mm | small | tops of the radial Ø4.4 insert holes and the centre Ø6.1 hole | none |

**So the plate is PLA only:** no supports, no PETG and no swaps. The PETG-interface rule (log 033) applies to supported prints.

**A1 bed fit:**
- At the bed centre the part spans X 22.9–233.1 and Y 3.1–253.0.
- Its bounding box reaches into the A1's head-wrap corner (X > 226, Y > 224), but the round outline doesn't: no vertex is in that corner.
- `make_plate_3mf.py` now checks the outline instead of the bounding box.

## The file

**Spec:** `sim/web/tools/plate_2nd_floor.json`, built by `make_plate_3mf.py`.

**Settings:**
- 0.16 mm High Quality base;
- 4 walls, 25 % gyroid, 6 top / 5 bottom layers;
- no brim, supports off;
- PolyLite PLA Pro at 215 °C, textured plate at 60 °C.

**Slice (Bambu Studio 2.8 CLI):** 8 h 29 min, 188 g PLA, 0 filament changes, no warnings.

**File:** `~/Downloads/gerdoo_2nd_floor_A1.3mf`.

## The antenna brackets on the same plate

**The user asked:** fit the antenna brackets onto this plate too.

**The brackets:** they come from the user's `anthenas` file. Each side is 3 overlapping bodies: an 80 × 21 × 6 bracket, a 36 × 30 × 3 arm and a 1 × 4 × 4 pin. Together they make one 46 × 80 × 6 part, flat underneath, with no overhangs.

**How they go into the file:**
- `make_plate_3mf.py` now accepts a list of STLs for one object. Bambu unions the parts of an object.
- One bracket sits in each arm-notch pocket, at X 3–49 and X 207–253, Y 88–168.
- They're 7.9 mm from the floor and clear of the head-wrap corner.

**Slice:** 9 h 13 min, 204.5 g PLA, 0 changes, no warnings.

## Found while checking the board placement (before printing)

**Placement is as planned (log 029):**
- The XVF3800 core board sits at the front, behind the chest, at world z 50–102.
- The USB hub sits at the back, between the antenna tabs, at z −46 to −104.
- The floor is turned 180° in the preview, so floor-local +z is the back.

**Problems in v9:**
- **The core board has no mounting holes.** Nothing in the floor matches its 4 × M3 on 62.5 × 44.2.
- **The hub pilots are Ø2.1 for self-tapping M2.5 standoffs.** That was chosen before the M3/M2-only rule. The hub's holes are Ø2.8, so M2 fits.
- **The two blind "antenna pin pockets" (Ø5 × 5, from the top) catch nothing.** I added them in log 030 for the pins in the user's antenna design. But those pins stick 1 mm *up* from the arm's top, not down into the floor.

**A third problem, found by the collision check:** the hub's rear holes (world ±29, −99) land on the arms of the antenna brackets. So the hub's rear standoffs would stand on the antenna arms.

## Options checked for the hub

| Option | Result |
|---|---|
| Turn the antennas further out, to ±25…35° | ❌ The brackets hit the 2nd→3rd corner posts |
| Move the hub forward | ❌ It runs into the UPS cells and the Jetson |
| **The user's idea:** hub at the front, sound board at the back | ❌ The mic ring's flat cable is 20 cm, but the route to the back around the Jetson's batteries is about 22 cm, and the display cable gets longer too. The sound board's back holes (±31.25) also land on the antenna arms. |
| **Hub 7.3 mm further back:** its rear holes (±29, −106.3) then sit on the antenna bolt holes (±28.5, −106.3; the arm's hole is Ø4.4) | ✅ **Chosen by the user.** Collision-checked against everything in the preview. |

## Changes to `2nd-floor-v2` (timeline 49 → 72)

**Sound board (XVF3800 core) at the front:**
- 4 × Ø9 × 5 mm bosses at floor-local (±31.25, −54.0 / −98.2). This is Seeed's pattern, 62.5 × 44.2; the board's holes are Ø3.3.
- M3 heat-set inserts, Ø4.4 × 7, from each boss top. They stop 2 mm above the underside.

**USB hub at the back:**
- **Removed:** the old M2.5 pilots and the antenna M3 insert holes are plugged.
- **Front pair:** 2 × Ø7 × 8 mm bosses at local (±29, 57.3), each with an M2 insert hole Ø3.2 × 8.
- **Rear pair:** M2 insert holes Ø3.2 × 8 at local (±29, 106.3), in the floor under the antenna arms' bolt holes.
- **One M2×16 per rear corner** goes through the hub, a printed 5 mm spacer, the antenna arm and into the floor insert. It holds both the hub and the antenna bracket.
- **Spacers:** modelled as 2 separate bodies in their real place, OD 6 / ID 2.4 × 5.

**Also:**
- The antenna pin pockets are filled. The user also dropped the pins themselves, so the bracket print uses only the bracket and the arm.
- The old front-centre Ø4.4 through hole under the sound board is plugged, as the user asked.

**Back-centre hole:** the old Ø4.4 hole at (0, −110) world, under the hub's back edge, was later plugged as well, after the user asked what it was for. Nothing uses it.

**Checks:**
- **Collisions:** the floor, spacers, raised sound board and moved hub are all clear. The one exception was already there: the UPS stand-in is 79 deep against the user's 78 mm pocket, and the real board already fits that pocket on the current floor.
- **Preview fit study:** the hub is moved back, the sound board is raised 5 mm, and the old hub standoffs are removed.

**Hardware for this floor:**
- **Sound board:** 4 × M3 inserts, 4 × M3×6 or M3×8.
- **Hub:**
  - front: 2 × M2 inserts, 2 × M2×6 or M2×8;
  - rear: 2 × M2 inserts, 2 × M2×16.
- **Corner posts:** 4 × M3 inserts, as before.
- **Covers:** 4 radial M3 inserts.

## Plate v3

**Parts:**
- floor;
- both antenna brackets, without the pins;
- 2 hub spacers in the back-left corner.

**Slice:** 9 h 20 min, 205.7 g PLA, 0 changes, no warnings.

**Overhangs:** unchanged. Everything added is on the top face.

## The antenna brackets become one piece

**The overlap:** at ±15° from the back (log 029 put them there once the arm notches took the floor's sides), each 80 mm curved band runs past the centre. The right one spans −3.5° to +33.5° and the left one −33.5° to +3.5°. They overlap by about 15 mm of arc (1.04 cm³), so the two printed brackets could never both go on. The user asked whether they were joined, and that is how this showed up.

**Decision (the user):** join them into one piece.

**`antenna-bracket-back-v1`:**
- It's the union of the user's two brackets and both arms as placed in the preview, without the pins.
- One solid: 146 × 53 × 6 mm, 18.4 cm³, flat underneath, no overhangs.
- It keeps both SMA holes (Ø6.3) and both bolt holes (Ø4.4). The bolt holes take the shared M2 hub screws.
- **Frame:** preview x/z, with y 0 at the 2nd floor top.
- **Preview:** the old bracket bodies are hidden. One body, "antenna bracket, back (one piece, print this)", replaces them.

**Printing:** at 146 × 53 it doesn't fit beside the floor, so it goes on the next plate, with the neck parts. STL: `antenna_bracket_back.stl` in the session's print folder.

## Plate v4 (final for the 2nd floor)

**Parts:** floor and the 2 hub spacers.

**Slice:** 8 h 35 min, 189.4 g PLA, 0 changes, no warnings.

## Plate v5: the 2nd→3rd separators added (the user asked)

**The posts:** 4 × `separator-2nd-short`, the user's design:
- hex, 17.8 mm across the corners, **74 mm**, with a Ø4.4 hole all the way through;
- 74 mm is the gap between the 2nd floor top (87) and the 3rd floor underside (161).

**Fit:**
- The 3rd floor (`3rd-floor-v2`) has Ø4.4 through-holes at (−60, ±90) and (65, ±90), the same corners as the 2nd floor. So all 8 corner posts stack in line.
- `separator-2nd-back` (60 mm) is from an older layout and isn't used.

**On the plate:** printed standing, two in each arm-notch pocket, at X 16 / 240 and Y 104 / 152.

**Slice:** 12 h 6 min, 240.0 g PLA, 0 changes, no warnings.

**A correction to log 036's hardware count:**
- At the 2nd floor, the lower post's top and the upper post's bottom meet at the same Ø4.4 corner hole. A screw head there would sit under the upper post.
- Join them instead with:
  - **either** a headless M3 stud, about 20 mm, between M3 inserts in both post ends;
  - **or** one M3 threaded rod through the whole corner stack (deck, lower post, 2nd floor, upper post, 3rd floor), with nuts and washers at both ends.
- Either way that's 4 fewer M3×20.

## The antenna bracket on its own plate

**Why not on the floor plate:** the one-piece bracket (146 × 53) doesn't fit beside the floor; the separators fill both notch gaps. Its band's inner arc matches the floor's R125 edge, but its arms would overlap the floor.

**The file:** `~/Downloads/gerdoo_antenna_bracket_A1.3mf` (spec `sim/web/tools/plate_antenna_bracket.json`):
- printed flat, no supports;
- 49 min, 15.4 g PLA, no warnings.
