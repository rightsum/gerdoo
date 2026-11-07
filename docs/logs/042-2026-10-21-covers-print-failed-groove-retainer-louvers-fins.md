# 042 — The covers print failed: a 2 mm light in a 1.3 mm groove, a loose retainer, messy vents, and a cover that fell over

| | |
|---|---|
| **Date** | 2026-10-21 |
| **Type** | Print failure → design fixes + print setup |
| **Status** | ✅ `front-cover-v1` v9 and `back-cover-v1` v8 saved · ✅ Two plates sliced, PLA only, 0 swaps · ⏳ Not printed |
| **Severity** | Medium: a lost 9 h print, and two parts that wouldn't assemble |

---

Follows [041](041-2026-10-20-front-cover-printable-inlays-and-display-plug.md) (the covers plate) and [030](030-2026-10-16-front-and-back-covers-and-the-cable-plan.md) (cover design).

## What the user found

The user printed `gerdoo_covers_A1.3mf` (both covers standing, the display retainer and the LDR cradle).

1. **The KA009 light didn't fit the smile groove.** The filament is **2 mm**; the groove was 1.3 wide. The length was right.
2. **The display retainer was loose at its edges and fell off.**
3. **The vents ("arrows") on both covers printed messy.**
4. **Partway up, a cover fell over** and took the rest of the plate with it.

## 1. The groove was sized for the wrong filament

**The wrong turn:** the inventory said "300 × 1 mm", from the vendor table's "H 1 mm" and Bambu Lab's product page (log 030). The listing's "2.2 mm" was dismissed. The user has the part in hand: it's 2 mm.

**Also found:** the groove was **0.55 mm off-centre** at both ends of the mouth.
- The lip was embossed onto the r 128 shell, and the groove onto the r 129.4 lip top.
- Emboss keeps arc length, so the same sketch x lands at a different angle on each radius. At s ≈ 60 mm that's 0.6 mm.
- At the mouth tips the groove's inner wall was down to about 0.4 mm.

**Fix (`front-cover-v1` v9):**
- **Groove 2.4 wide × 2.0 deep** (was 1.3 × 1.4), centred in the 4.4 mm lip: 1.0 mm walls each side, the floor at r 127.4.
- The groove sketch is redrawn as the lip's own outline offset 1.0 mm in from each side. Its x is scaled by 129.4 / 128 so the wrap lands on the lip's angle.
- **Measured on the model:** walls 0.98 / groove 2.42 / walls 0.98 at 12 stations round the loop.
- **Filament hole** at the right tip: 1.5 × 4.5 → **2.6 × 5.6**, so both 2 mm strands pass (lead out, tail back in).
- The old groove emboss is suppressed. Fusion wouldn't accept new profiles on it (`!profs.empty()`), and offsetting its NURBS walls failed, so a new emboss sits before it in the timeline.

**Printing:** the groove's ceiling is now a 2 mm horizontal overhang where the smile is flat. It's hidden under the filament; if it sags, run a 2 mm drill bit along it.

## 2. The retainer had nothing proper to hold it

**How it was held:** 2 × M2×6 self-tapping screws into Ø5.5 × 1.5 mm posts with Ø1.7 pilots, printed with their axes horizontal. The posts stop 0.2 short of the retainer, for preload. That's very little plastic for a self-tapper, and nothing holds the retainer before the screws bite.

**Fix:**
- The posts become **Ø7 bosses with M2 heat-set insert holes, Ø3.2 × 4.0**, the user's M2 insert size (the hub uses it).
- Same height: the boss face is at z 123.9, still 0.2 short of the retainer.
- 1.5 mm of plastic is left in front of the hole, so the insert can't push through to the bowl face.
- Ø7 stays inside the mic ring's Ø52.5 opening (r 24 from the centre) and clear of the display pocket (1.0 mm).
- **Hardware:** 2 × M2 heat-set inserts, 2 × **M2×6 machine screws** (or M2×5), plus the 4 × M2×4 into the display's brass standoffs as before. The retainer itself is unchanged.

## 3. The vents had flat, floating ceilings

**Why:** the covers print standing, so a slot cut straight through the 2.4 mm wall gets a ceiling with the slot's own slope.
- **Chevrons:** 21°.
- **Back vents:** 18°.

Both are far below 45°. The chevrons are worse: they point down, so each ceiling starts as an island at the V tip and grows outward into air.

**Why not supports, as the user suggested:**
- A support inside a 2.2 mm slot can't be pulled out.
- A PETG interface on 3 × 50 layers of ceiling means about 100+ swaps (log 041).

**Fix: 50° louvers.**
- Each slot is cut as an oblique prism that drops 1.19 mm for every mm it goes inward: a sweep with the profile kept parallel, along (0, −tan 50°, ∓1).
- **Outside:** the openings are exactly where they were. The profile is pre-shifted per x by (z₀ − z_surface)·tan 50°, so the cut meets the r 128 face on the old outline.
- **Ceilings:** now at least 50° steep, and **highest at the outer face**, so the visible edge is supported from inside. The only leftover island is at the inner face of each chevron tip, which is hidden.
- **Through-view:** the slot drops 2.9 mm across the wall, more than its 2.4 mm height. You no longer see straight through, but air still passes.
- **Each tool is clipped to the shell** (r 125.2–128.6) before cutting, so nothing behind the shell is touched.
- **Measured on the STLs:** down-facing area flatter than 30° in the vent zones:
  - front: **341 mm² → 0**;
  - back: **548 mm² → 0**.
- **Fusion:** a sweep of several profiles makes several bodies. A join won't merge bodies that don't touch, so each one is clipped by its own intersect (keeping the annulus), then all of them go into one cut, and a Remove deletes the annulus.

## 4. The front cover toppled: snap-off fins and separate plates

**The cause:**
- The front cover is a 2.4 mm wall **181 mm tall** on a bed-slinger, standing on about 225 mm² of edge with a 6 mm brim.
- Above y 81 the mic cup hangs 35 mm inward.
- The curled vent ceilings (3.) were in the nozzle's path lower down.
- Both covers were on one plate, so one falling ruined both.

**Fix:**
- **Stabilizer fins** (`sim/web/tools/stabilizer_fins.py`):
  - triangles 1.6 thick on the hidden inner side, standing on the bed;
  - **front:** 4 fins at ±24° and ±36°, up to y 45, 30 mm wide at the bed;
  - **back:** 2 fins at ±38° up to y 40, and 2 low ones at ±13° up to y 6.
- **How they attach:** each fin stops 0.6 mm short of the shell and joins it through 1.5 mm tabs every 8 mm. Snap them off; the nubs are on the inner face.
- **Checked against the Fusion bodies:** no fin sample point is inside a cover, and 40 of the 44 tabs are anchored in the shell. The 4 that aren't are low tabs at ±36° (front) where the bottom corner curves up; the fin is still held by its other tabs.
- **They go in as parts of the cover object** (`make_plate_3mf.py` STL lists), so the 8 mm brim runs round the fins too.
- **One cover per plate:** if one fails, it can't take the other down.

**Avoided:** the outer ±40° fin positions put the bottom tabs where the front cover's bottom corners curve up (the shell starts at y −8 at x 80). They moved to ±36°.

## The files

| File | Parts | Slice |
|---|---|---|
| `~/Downloads/gerdoo_front_cover_v2_A1.3mf` | front cover v9 + 4 fins, standing | **6 h 37 min, 108.5 g**, 0 changes |
| `~/Downloads/gerdoo_back_cover_v2_A1.3mf` | back cover v8 + 4 fins, standing; display retainer; LDR cradle v7 | **3 h 32 min, 60.7 g**, 0 changes |

- **Specs:** `sim/web/tools/plate_front_cover.json` and `plate_back_cover.json`.
- **Settings:** 0.16 HQ, PLA only, supports off, **8 mm outer brim**.
- **Slicer warning:** only the front cover's usual "floating regions" warning, for the hidden bridges listed in log 041.
- **Both on one plate, if wanted:** `~/Downloads/gerdoo_covers_v2_A1.3mf` (spec `plate_covers.json`): both covers with their fins, the retainer and the LDR cradle. **9 h 38 min, 169.1 g**, 0 changes. That's 31 min less than the two plates. The cost: a failure at any height can still take down both covers, and the back cover finishes at y 86 but stays on the bed beside the front cover for another ~3 h. The failed `gerdoo_covers_A1.3mf` is deleted. The new files carry a `_v2` name, because overwriting in place kept Finder's old "Date Added" and buried them.

## Takeaways

- **Measure the part in hand before trusting a vendor table.** "H 1 mm" was not the filament's diameter.
- **Emboss keeps arc length per target face.** Two embosses on different radii drift apart by (Δr/r)·s; scale x by r₂/r₁ to line them up.
- **For a part printed standing, a slanted slot's ceiling is the slot's own slope.** Below 45° it needs a louver, not support, and the louver must rise toward the visible face.
- **Tall thin parts on the A1:** fins tied on with tabs, a wide brim, and one per plate.

## The louvers failed too: the arrows are now blind recesses (2026-10-23)

**What happened:**
- The user printed the front cover with the 50° louvers, and the arrows came out messy again.
- After the first print the user had said supports were needed. I swapped in louvers instead of fixing what actually failed.

**Why the louvers failed:**
- A louvered slot runs diagonally through the 2.4 mm wall. In any one layer it shows up as a short slanted gap, and the opening moves along the face by 0.41 mm every layer.
- The slicer wraps short perimeter loops round each little gap, with travel and retraction between them, and that leaves blobs and strings on the visible face.
- So the overhang angle was never the real problem. The real problem is a narrow slot going through a thin wall that stands upright on the bed.
- Supports can't fix it either. You can't pull support out of a 2 mm slot, and a PETG interface would need hundreds of swaps.

**The fix:** the arrows don't go through any more.
- **Front:** the 3 chevrons are a **1.2 mm deep recess**, embossed onto the r 128 face. The louver chain (sweep, annulus, combines) is deleted.
- **Back:** the 8 gills are recesses about 1.3 mm deep.
  - **How:** a straight cut trimmed to an annulus from r 126.8 out to r 135, since Fusion's emboss refused there ("Cannot emboss near some features").
  - **Material left behind them:** about 1.1–1.2 mm.
- **Why recesses print:** the only overhang left is each recess's top edge, a ledge 1.2–1.3 mm deep held by the solid back of the recess. Nothing starts in mid-air.
  - **Down-facing surface in the arrow zones:** front 169 mm², back 274 mm², all in 1.2 mm ledges.
  - **Floating check:** 0 regions in the arrow zone. The front cover's remaining Bambu warning is the known hidden bridges (display pocket etc.).
- **What's lost:** the airflow through the arrows. The 1st floor is open at both sides.

**Files:**
- `front-cover-v1` and `back-cover-v1` saved.
- **Plates** (STLs re-exported to `build/print/`, fins regenerated):

| File | Contents | Time | PLA |
|---|---|---|---|
| `~/Downloads/gerdoo_front_cover_v3_A1.3mf` | front cover | 6 h 39 min | 109 g |
| `~/Downloads/gerdoo_back_cover_v3_A1.3mf` | back cover + retainer + LDR cradle | 3 h 33 min | 61 g |
| `~/Downloads/gerdoo_covers_v3_A1.3mf` | both covers on one plate | 9 h 41 min | 170 g |

- The v2 plates are removed.

**Takeaway:** don't cut through-slots into a thin wall that's printed standing, at any angle. Make features on visible upright faces as blind recesses, or as separate flat inlays.

## Wider covers: hiding the motor drivers and the side walls (2026-10-23)

**The user asked:** since the covers are being reprinted anyway, extend both further round the sides. The motor drivers showed at the front, and the side walls at the back.

**How far each cover can wrap:**
- **The arm only limits the covers above about 110 mm.** I measured each arm's reach from its J1 axis by height, on the ElRobot model:

  | Height | Reach from the J1 axis | Cover may wrap to (6 mm margin) |
  |---|---|---|
  | y 40–100 | ≤ 47 mm | ~69° |
  | y 100–110 | 26 mm | ~79° |
  | y 110–130 | 103–106 mm (upper arm) | ~43° |

- **Near the deck, only the static arm base is in the way.** It reaches 55–68 mm from the J1 axis.
- **Choice:**
  - **front:** **±62°** up to y 92, then a slope back to the old edge (88.7, 109). The top above y 109 is unchanged.
  - **back:** **±60°** over its full height (to y 86).

**How it's built:**
- **Why not edit the outline:** the base shape and the outline couldn't be edited. Re-pointing the `shell` extrude at a redrawn profile fails with `curProfile`, and the rolled-back script left `shell` on cached geometry. The front cover was closed without saving and reopened.
- **Instead:** a TBRep piece is joined at the end of each timeline:
  - annulus r 125.6–128;
  - angular wedges 41°→62° (front) and 41°→60° (back), from half-space boxes;
  - a sloped top cut;
  - rounded outer corners (r 18 front; r 14 / 8 back);
  - **fillers** for the old rounded bottom corners (and the back's top corners), so no notches remain.
- **What it doesn't touch:**
  - The pieces start at 41° and the fillers stay low, so they clear every screw hole (the outermost are at ±30°) and every recess.
  - The old 1 mm round on the side edges is buried in the join.
  - The new edges are sharp.

**A trap I fell into:**
- With the preview open, `documents` held **older linked copies** (front-cover v7 and v9, back v5 and v8) under the same names. The first join went into the linked v7.
- **Fix:** I closed the preview without saving and closed the stale copy. I now pick the top-level document by checking that `isUpToDate` doesn't raise.

**Checks:**
- **Clash check against the preview (579 bodies):** the front has none.
- **The back's only overlap is the dock's stop pads (1542 mm³), at 35–41° from the back.** That's the old cover range, caused by a stale dock position: the pads moved in log 041 so the robot parks 3.48 mm further out. With the dock shifted −3.48 mm in z the overlap is **0**. The preview's dock is moved to that real position.
- **Floating check:** nothing new on the front. On the back, 3 cells of ≤ 6 mm² sit 0.5 mm above the bed at the new rounded bottom corners, which is harmless.

**Files:**

| | Version |
|---|---|
| `front-cover-v1` | v11 |
| `back-cover-v1` | v10 |
| preview | v43 (refs updated, dock moved) |

| Plate | Time | PLA |
|---|---|---|
| `~/Downloads/gerdoo_front_cover_v4_A1.3mf` | 7 h 36 min | 134 g |
| `~/Downloads/gerdoo_back_cover_v4_A1.3mf` (with the retainer and LDR cradle) | 4 h 18 min | 81 g |
| `~/Downloads/gerdoo_covers_v4_A1.3mf` | 11 h 22 min | 215 g |

- All PLA only, 0 swaps. The front cover is now **226 mm** across on the bed.
- v3 removed.

**Note:** the wider back cover also covers the side walls' boards. Take it off (its screws) to reach their terminals.

**The ends lifted off the bed (the user, printing the wider covers):**
- **Cause:** I'd given the extensions rounded bottom corners (r 18 front, r 14 back). Printed standing, each corner rose from the bed at a near-horizontal tangent, so the outer ~14° of each wing started in mid-air at the far end of a long thin arc. It curled and pulled the end off the bed.
- **I'd missed it:** my overhang check flagged it on the back (3 small spots 0.5 mm above the bed) and I called that harmless. A floating start at the end of a long thin wall is never harmless.
- **Fix:** square bottom corners. A filler wedge from 46.5° to 62° (front) and 47.5° to 60° (back), up to y 9 / 5, joins on, so each wing stands on the bed all the way to its end. The front cover is now v12 and the back cover v11.
- **Extra snap-off fins near each end:** ±56° on the front, ±54° on the back, so 6 per cover.
- **Checks:**
  - fin samples outside the covers;
  - all tabs anchored (front 40/40, back 28/28);
  - no clashes with the arm bases, drive, electronics, holders or the dock;
  - overhang check: nothing near the ends.

| Plate | Time | PLA |
|---|---|---|
| `gerdoo_front_cover_v5_A1.3mf` | 7 h 48 min | 137 g |
| `gerdoo_back_cover_v5_A1.3mf` | 4 h 30 min | 84 g |
| `gerdoo_covers_v5_A1.3mf` | 11 h 46 min | 221 g |

v4 removed.

**The v5 front cover toppled at layer 535 (Z 85.8, y 75.8):** the nozzle hit the part. A toppled part can't be resumed.
- **What printed just below that layer:**
  - overhang walls and bridges at y 72.6–73.7, x ±51–56: the smile lip's end caps and the top of the lead-out hole;
  - a bridge at y 64.4: the KA009 cradle roof, a 1.2 mm ledge 12 mm long.
- **Probable cause:** the new side wings are free-standing 2.4 mm walls up to y 92. The end fins only reached y 40, and the A1's bed swings them along the arc (Y). A slightly curled edge plus a whipping wing end makes a nozzle strike, and an 85 mm thin cover can't take one. The first-ever covers print also fell at about half height.
- **Fixes:**
  - **Taller fins:**
    - front: ±56° to y 80 (24 wide), −36° / ±24° to y 70, +36° stays at 45 (the KA009 cradle sits above it at y 52–66);
    - back: ±54° to y 75.
    - All fin samples are outside the covers; every tab is anchored (front 59, back 38).
  - **Gentler motion:**

    | Setting | Was | Now |
    |---|---|---|
    | travel acceleration | 10000 | 3000 |
    | default acceleration | 4000 | 2500 |
    | inner walls | 150 mm/s | 100 mm/s |
    | travel | 700 mm/s | 400 mm/s |
    | z-hop | 0.4 Auto Lift | **0.8 Spiral Lift** |
    | `reduce_crossing_wall` | off | on |

    All are confirmed in the G-code header. The outer walls were already at 60.
- **Files (v5 removed):**

  | Plate | Time | PLA |
  |---|---|---|
  | `gerdoo_front_cover_v6_A1.3mf` | 10 h 21 min | 141 g |
  | `gerdoo_back_cover_v6_A1.3mf` | 5 h 55 min | 86 g |
  | `gerdoo_covers_v6_A1.3mf` | 15 h 43 min | 227 g |

  The z-hop keys are printer settings. If the Bambu GUI resets them to its preset, the rest still applies.

> **Correction (2026-11-07, log 050):** this section is based on a misunderstanding. The part that toppled on 2026-10-25 was the **neck's head yoke**, not the front cover. Its fix (the yoke printed on its back) is in log 035. Front cover v7's braces, described below, are harmless and stayed in the plate.

**Second topple, at ~80 % (2026-10-25):** the user reports the nozzle hit the front cover again, around 80 % of the print, and it fell.
- **Where that is:** from the G-code's M73 progress, 80 % of the print time is layer 847 (Z 135.7, y 125.7).
- **What printed just below:** only small features:
  - the eye bosses' 1.2 mm ledges (y 122–131.5, x ±60);
  - the undersides of the retainer bosses (y 120.6);
  - the tops of the insert holes (3.2 mm bridges, y 125.7).

  The large hidden bridge (the display pocket roof, 20.8 mm) comes later, at y 143.8 (88 %).
- **Likely cause:** the cover itself. By then it's a 145 mm thin arc carrying the heart and cup, which hang 35 mm inward. The fins stopped at y 70–80, so the top half was unbraced and swung with the bed until the nozzle clipped it.
- **Fix:** the ±36° fins are replaced by **±40° braces up to y 120** (32 mm wide on the bed).
  - They stay clear of the cup (x ≤ 37) and the KA009 cradle (29–36°): all 462 fin samples are outside the cover, and all 74 tabs are anchored.
  - Fins now: ±56° to y 80, ±40° to y 120, ±24° to y 70.
- **Plates:** `gerdoo_front_cover_v7_A1.3mf` (10 h 44 min, 145 g) and `gerdoo_covers_v7_A1.3mf` (16 h 6 min, 231 g). v6 front and combined removed. The back cover plate stays v6.
- **Also to check (the user's photo):** the AMS lite is top-mounted. If its PTFE tubes hang low at high Z, they could brush the top of a tall part. Watch it at ~130 mm.

## The retainer's ears were never attached (2026-10-29, `front-cover-v1` v13)

**The user's report:** the printed display retainer fell apart at the sides. Its ears looked as if they weren't joined to anything.

**Cause:**
- A **0.5 mm slit** ran the full height of each ear, at |x| 15.25…15.75, between the ear (|x| 15.75…24, y 120…128) and the frame.
- Fusion counted the body as one lump, so nothing flagged it. But in print, each ear was a separate piece.
- The same slit probably explains why the first retainer "was loose at its edges and fell off" (section 2). That's not checked against the older versions.

**Fix:**
- The ears are now 10 × 12 mm (|x| 14…24, y 118…130), solid into the frame, 2 mm thick. The Ø2.4 holes are re-cut at (±20.5, 124).
- **Checks:**
  - 0 mm³ overlap with the cover;
  - the slit is closed and the holes are open (probed);
  - the ear corners sit at r 24.7 from the display centre, inside the mic ring's r 26.25 hole.

**Print:**
- `~/Downloads/gerdoo_display_retainer_A1.3mf`: flat, 100% zig-zag, **15 min, 1.9 g**. (Gyroid can't be used at 100% density.)
- `display_retainer_v13.stl` replaces v10 in the covers' plate specs.
