# 036 — Arm bases made printable without neck supports, plus the separators on one plate

| | |
|---|---|
| **Date** | 2026-10-18 |
| **Type** | Design change for printing + print setup |
| **Status** | ✅ Arm bases redrafted (`gerdoo-assembly-preview`, saved) · ✅ `gerdoo_arm_bases_separators_A1.3mf` slices cleanly · ⏳ Not printed |
| **Severity** | Low |

---

Follows [033](033-2026-10-17-printing-the-1st-layer-on-the-a1.md) (printing rules) and [035](035-2026-10-17-sts3215-neck-and-taller-lidar.md).

## What was asked

The user proposed printing the two arm bases and the 1st→2nd floor separators together on one bed.

## The problem with the arm bases as designed

**Shape:** each base (log 029) is a foot on the deck, a lofted neck leaning out over the wheel, a Ø90 disc and ElRobot's J1 housing, all one part.

**Orientation:** only as mounted (foot down) does the part sit flat on the bed: 1530 mm² of contact. Every other tilt in 15° steps gave under 400 mm².

**But as mounted,** the neck's outer side leans out at about 21° from horizontal, all the way from the foot to the disc rim. That gives overhang on 229 of the 0.16 mm layers. With the PETG interface, which is now the rule (log 033), that's roughly 460 filament swaps.

**Considered and dropped:** splitting the base into a pedestal (printed disc-down, no supports) and a J1 housing. The housing has only thin walls and a partial floor where it meets the disc, so a bolted joint there would be the weak point.

## Fix: a 45° draft under the outer half of the neck

**What was added:** the `Arm base (merged, concept)` component gets a base feature and two cut combines (L and R) at the end of its history:
- 13 cutting planes, every 15° around the outer half of the foot's ellipse (x 77.4–117.4, z ±26).
- Each plane is tangent to the ellipse and tilted 45°.
- Everything outside them and below the disc's underside (y 29.6) is removed.

**Untouched:** the foot, the M4 insert holes, the disc, the support lobe and the J1 housing.

**Result:** 201.7 → 155.3 cm³ per base, still one solid each.

**Remaining overhang below 40° (as mounted):**

| Height | Area | What |
|---|---|---|
| 7 mm | small | M3 insert hole ceilings, small bridges |
| 30 mm | 3621 mm² | the disc's flat underside, **the only supported area** |
| 52–53 mm | 101 mm² | housing bridges |
| 86–88 mm | 384 mm² | housing bridges |

**Strength:**
- J1 sits at x 145.7, right at the neck's new outer edge (147 at the disc).
- The housing is on the inner side of J1, so the arm's load still comes straight down the neck.
- Log 029's bending stress in the neck was about 0.2 MPa, so the thinner neck isn't a concern.

**Fit:** material was only removed, so there are no new clashes. The tyre gets more clearance.

## The plate

**Builder:** `sim/web/tools/make_plate_3mf.py`, a general multi-object builder on top of `make_print_3mf.py`'s settings. The spec for this plate is `sim/web/tools/plate_arm_bases_separators.json`.

**Parts:**

| Part | Qty | Orientation | Supports |
|---|---|---|---|
| arm base L / R | 2 | as mounted, foot down | trees under the disc only, enforced, with a 2-layer PETG interface |
| `separator` hex post, 77 mm | 4 | standing | none |
| round post Ø16 × **80**, same design as the user's `seperator-circle`, lengthened | 2 | standing | none |

**Settings:**
- 0.16 mm High Quality base.
- **5 walls, 40 % gyroid** (log 029's recommendation for the M4 insert foot).
- Support angle 40°.
- PolyLite PLA Pro in slot 1 at 215 °C, the user's black PETG in slot 2 at 240 °C, bed at 60 °C.

**Slice (Bambu Studio 2.8 CLI):** 23 h 34 min, 342 g PLA + 4 g PETG, **20 swaps**, no warnings.

**Round post length:**
- **First version:** used the user's `seperator-circle` file, which is 63 mm. The user spotted that the centre posts came out far shorter than the 77 mm hex ones.
- **Measured in the preview:**
  - The posts stand on the deck top at (±47.7, 0), with a small screw hole through the deck.
  - Their tops drop into **Ø17 × 3 mm recesses** in the 2nd floor's underside, at 77–80 mm.
- **So they must be 77 + 3 = 80 mm,** which is what the preview's stand-in already was.
- **What 63 mm is for:** probably an older layout. `seperator-circle-2nd` turned out to be an empty design.
- **Fix:** the plate now carries an 80 mm post generated in Python. It's the same Ø16 cylinder with a Ø4.4 hole all the way through. The user's file is unchanged.

**File:** `~/Downloads/gerdoo_arm_bases_separators_A1.3mf`.

## M3, not M4, and the two inner bolts (the user's catch)

**M4 was my mistake.** Log 029 read the motor pockets' Ø4.4 holes as M4 clearance. Ø4.4 is the user's **M3** heat-set insert size, and the whole robot uses only **M3 and M2**. The 36GP-555 brackets are already held by M3 bolts from below with nuts on top.

**The inner two holes were broken.** They sit right on the foot's ellipse edge: at z ±14.8 the foot reaches in only to x ≈ 81, and the old Ø5.6 hole's edge was at x 82.1. So they were cut half open, with 0–1 mm of plastic around them. The user found that only two of the four could hold anything.

**Fix**, added at the end of the arm-base history; nothing earlier was changed:

| Holes | Before | Now |
|---|---|---|
| Outer two (x 109.9, z ±14.8), neck above | M4 insert Ø5.6 × 10 | filled, re-cut as **M3 heat-set insert Ø4.4 × 7**. The bracket bolt comes up from below into it. |
| Inner two (x 84.9, z ±14.8), open above | M4 insert Ø5.6 × 10, half open | **Ø11 × 8 boss** with an **M3 clearance Ø3.4 through** and an **M3 hex nut pocket open at the top: 5.45 AF × 3 deep**. The user's kit nuts measure 5.2 across the flats with calipers (below the standard 5.5), so the pocket is the nut plus 0.25. A first 5.7 AF pocket would have let them rattle. The nut drops in from above; the bracket bolt from below screws into it. |

**Checks:**
- Both bases are still one solid each, 156 cm³.
- Section through the bolt row looks right.
- No clashes with the IBT-2s (they start at z 25; the bosses reach z 20.3), the drive or the deck.

**Strength with M3:** worst pull per fixing is about 117 N with all 4 in use (log 029).
- An M3 brass insert in PLA holds roughly 400 N or more, so about 3.5×.
- The inner pair are bolt + nut, limited by the bolt (about 2.8 kN).

**Re-sliced:** 23 h 40 min, 343 g PLA + 4 g PETG, 20 swaps, no warnings.

## Hardware

- **Arm bases, per base:**
  - 2 × M3 heat-set inserts (Ø4.4 × 7) in the outer holes, pressed in from below.
  - 2 × M3 nuts in the inner pockets, dropped in from above.
  - All 4 bracket bolts are **M3×20 socket caps** from below, from the user's 540-piece stainless kit.
  - Each outer hole has a Ø3.4 clearance continuing above the insert, up to y 14. An M3×20 reaches about 10.5 mm into the foot (bracket about 2.5 mm, plus 7 mm of deck at the pocket), so without it the screw would bottom out in a 7 mm hole before clamping.
  - At the inner holes the tip ends about 3 mm above the nut, in open air.
- **Separators:** 10 × M3×20 (4 hex posts × 2 ends, plus the 2 round posts at the bottom only, since their tops sit in the recesses). Use flat washers under heads that sit on plastic.
- **This plate uses 18 of the kit's 20 M3×20s**, plus 4 M3 nuts and 16 M3 heat-set inserts. Order more M3×20 (and some M3×16) before the 2nd→3rd floor and cover assembly.
- **Separators:** Ø4.4 M3 inserts in both ends, as before.
- **After mounting:**
  - The J1 housings are already turned 70° outward (log 032), so recalibrate J1 (panel Calibrate…) and redo its `RANGE`.
  - Check that J1's servo cable reaches.

## Still open

- The simulator's arm-base mesh still shows the pre-draft neck. Update it with the next sim deploy.

## Print 1 (2026-10-18): one arm base's support fell over at the first PETG layer

**What happened:** shortly after the PETG interface started under the disc (about 30 mm up), the support under one arm base fell over.

**The user's guess was bed temperature. It wasn't:**
- The sliced G-code sets the bed once (`M140 S60`, then `M190 S60`) and switches it off at the end. Filament swaps never change it.
- The PETG layers are 30 mm above the bed.

**Two things did go wrong.** The GUI showed the stock "PolyLite PLA @BBL A1" (220 °C, 65 °C bed, 15 mm³/s) instead of the file's PLA settings, most likely from syncing the AMS slot. That doesn't explain the fall. What does, from the G-code:
1. **Organic tree supports** under a large flat underside 30 mm up: thin branches, with the first PETG layer laid on their tips. PETG barely bonds to PLA, which is the whole point of the interface, so a dragged line can snap a branch.
2. **No prime tower** (dropped for the 1st layer, log 033). At each swap the A1 heats to 270 °C to purge into the chute and then prints PETG straight away, so the first lines and any ooze blob go right onto those tips.

**v2 (`gerdoo_arm_bases_separators_A1_v2.3mf`):**
- **Normal grid supports** (`normal(manual)`, `grid`, base spacing 2 mm, still enforced under the discs only), so there's a solid PLA lattice with a flat top under the PETG.
- **Prime tower:** 35 mm wide, no rib walls, at X 205, Y 8, the free front-right corner.
- **Interface printed at 40 mm/s.**
- **Slice:** 22 h 49 min, 367 g PLA + 9 g PETG, 20 swaps, no warnings.

**Lesson, for the print rules:** for PETG-interface supports, use **normal/grid supports under large flat overhangs** and **keep a prime tower whenever the plate has room**. Trees are for small or curved overhangs.
