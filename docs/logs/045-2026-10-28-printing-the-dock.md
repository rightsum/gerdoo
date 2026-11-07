# 045 — Printing the dock: the mast had no fixing, and three plates

| | |
|---|---|
| **Date** | 2026-10-28 |
| **Type** | Print preparation, plus a design fix found on the way |
| **Status** | ✅ `charging-dock-v1` v13 saved (v11: mast fixing; v12: plate slots; v13: inner rails removed; v14: stop pads removed, no supports) · ✅ 3 plates sliced: cradle 9.1 h, sign 12.6 h, letters 28 min · ⏳ Not printed · ⏳ The preview still links dock v10 |
| **Severity** | Medium: printed as v10, the mast would have stood loose on the cradle |

---

Follows [031](031-2026-10-16-simulator-physics-dock-and-assembly-fixes.md), [032](032-2026-10-17-measurements-dock-sign-and-arm-mount-angle.md), [035](035-2026-10-17-sts3215-neck-and-taller-lidar.md) and [041](041-2026-10-20-front-cover-printable-inlays-and-display-plug.md).

## The mast had no fixing

**Found while preparing the print:**
- The mast's 5 mm foot flange sat **inside** the cradle top: 48.1 cm³ of overlap.
- **Cause:** the cradle grew from 110 to 115 mm tall in log 032 (for the copper plates), and the mast was never moved up with it.
- The feature was called "fin foot flange (4x M4 into the cradle top)", but no screw holes were ever modelled. M4 is out anyway (M3/M2 only).
- Printed as it was, the mast would stand loose on the cradle, and the sign would sit 5 mm higher than modelled.

**Fix (`charging-dock-v1` v11, 5 features at the end of the timeline):**
1. A copy of the buried flange is lifted 5 mm onto the cradle top and joined to the mast.
2. Everything of the mast below the cradle top (y 48.3) is cut away. The sign keeps its modelled height, so the lidar V stays in the C1's scan band.
3. **4 × Ø3.4 clearance holes** through the flange, at x ±40 and ±85, z −190. They are clear of the ribs (x ±70) and of the fin's wire groove (x 0).
4. **4 × Ø4.4 × 7 insert holes** in the cradle top, under them. The cradle is solid there, from y 13.3 to 48.3.

**Check:** the mast and cradle now overlap by 0 cm³, and the timeline has no errors. The save was checked: version 10 went to 11.

The wire from the sign's LED groove now leaves the groove at the flange top. It crosses the flange's back edge and drops into the Ø8 hole 4.5 mm behind it.

## How each part prints

Floating-region check (`check_floating.py`) for each candidate orientation:

| Part | Orientation | Unsupported | Result |
|---|---|---|---|
| Cradle | upright (floor down) | **24,072 mm²**: the ceiling of the weight cavity | ❌ |
| Cradle | **upside down** (top on the plate) | the 2 stop pads (54 mm² each), small pocket ledges | ✅ Supports only under the pads |
| Mast | **standing**, flange down | only the tops of the M3 holes | ✅ |
| Sign head | standing | 9,833 (light box ceiling) + 8,924 (sign box underside) + 1,937 (V notch) + the ribs; the light-line slot becomes a **190 mm bridge** | ❌ |
| Sign head | upside down | the top isn't flat (the back 2/3 is 2.3 mm lower), so 8,928 floats just above the plate | ❌ |
| Sign head | **on its side** (−x end down) | the fin's free end (1,002), both ribs' lower faces (324 each). The light box's end wall becomes a 30 mm bridge, which is fine | ✅ 3 small supports |

## Plates

All three use the user's PolyLite PLA Pro, with the PETG support interface in slot 2.

| File (`~/Downloads`) | Contents | Time | Material | Swaps |
|---|---|---|---|---|
| `gerdoo_dock_cradle_A1.3mf` | Cradle (v12) upside down, PETG interface under the stop pads, prime tower | **9 h 4 min** | 312 g PLA + 4.8 g PETG | 26 |
| `gerdoo_dock_sign_A1.3mf` | Mast standing + head on its side, brim 6, gentle accelerations (tall parts). **2026-10-29: normal supports instead of tree, at the user's request (log 053): 12 h 25 min, 368 g + 1.6 g PETG, 8 swaps** | **12 h 37 min** | 363 g PLA + 1.4 g PETG | 6 |
| `gerdoo_dock_letters_A1.3mf` | 6 letters face down (textured face out), light-line diffuser flat, XY −0.08 so the letters press into the 0.6 recess | **28 min** | 7.1 g | 0 |

**Getting the times down.** The first slice took 24.8 h (cradle) and 39 h (sign), because of the 0.16 HQ preset's slow walls and the solid blocks.

| Change | Cradle | Sign |
|---|---|---|
| 0.16 HQ, 4 walls, 15% gyroid | 24.8 h | 39.0 h |
| 0.20 mm layers, 3 walls, 12% gyroid | 16.7 h | 27.3 h |
| + Standard-preset speeds (the sign keeps its gentle accelerations, and loses the prime tower for its 6 swaps) | 13.6 h | 20.5 h |
| + lightning infill; the sign no longer avoids crossing walls (z-hop stays) | **8.9 h** | **12.6 h** |

Lightning infill is enough here: the parts are static, and the dock gets weighed down anyway. Wall time is now the biggest share.

Specs: `sim/web/tools/plate_dock_{cradle,sign,letters}.json`. STLs: `build/print/dock_*_v11.stl`.

## Assembly

1. **Inserts:** 4 × Ø4.4 in the cradle top, plus 2 in the head's half-lap (already in the design).
2. **Mast onto the cradle:** 4 × **M3 × 10** with washers. Do this **before** the head goes on, because the head hangs over the screws.
3. **Head onto the mast:** 2 × M3 × 10 from the back, through the tongue.
4. **Letters:** press them into the recess (glue if loose). Slide the diffuser into the slot under them.
5. **Contacts, switch, jack and light:**
   - The plates slide into their slots with the wire soldered on (see the v12 section below; no screws, no holes in the copper).
   - KW11 in its pocket, DC-022B in the left wall, light as in log 032.
6. **Weight:** steel washers in the cradle cavity, and rubber feet.

## The copper plates: slide-in slots, clear of the jack and the switch (v12)

**The user's situation:** the plates are already cut to 34.2 × 43.7, and there's no way to drill them. The user can solder.

**Two faults found in the old pockets while checking this.** Neither had shown up before, because the plates were never modelled as bodies.
- **The robot's DC jack hits both plates.**
  - The pockets ran from x ±2.75 to ±37.25. The jack sits at x 0, and its metal thread (Ø7.2) passes the plate-face plane when the robot is docked.
  - So the thread would touch both plates' inner edges by about 0.8 mm.
  - The jack's body is metal, so touching the live plate is a **19 V short**.
- **The plates' inner bottom corners sat over the presence switch's pocket** (x ±10.5, y ±5.5), right next to the KW11's metal lever.

**`charging-dock-v1` v12** (2 combine features on a base feature at the end of the timeline):
- **The old pockets are filled** back to the r 131 face. The jack pocket and the switch pocket stay open.
- **Each plate slides into a slot from the top:**
  - slot x ±11.5…±46, 34.5 wide and 1.6 deep (the plate is 1.5);
  - a window x ±13.5…±44 leaves a **2 mm lip along both long edges**;
  - the slot's bottom is at y 0, so the plate rests at y 0…43.7, centred on the pins (y 22).
- **The inner lip stands on a printed rail** (x ±10.5…±13.5). There, the curved face lies below the plate.
- **Pins at x ±20** now land 8.4 mm from the plate's inner edge. The jack pocket only allows ±4.4 mm of sideways play, so that's enough.
- **Wire:** a 3 × 2 mm groove runs over the cradle top from each slot, then a Ø4 hole goes down at (±30, z −146) into the hollow.

**Checks (all 0 mm³):**
- a 34.2 × 43.7 × 1.5 plate in each slot;
- the jack's zone (r 8 around the jack axis);
- the switch pocket;
- the cradle against the parked robot's back cover.

The lips are where they should be (probed). Floating check upside down: only bridges over the window ends (30.5 mm, between the lips) and over the grooves.

**Cradle plate re-sliced:** 9 h 4 min, 312 g PLA + 4.8 g PETG, 26 swaps. `~/Downloads/gerdoo_dock_cradle_A1.3mf` replaced. The STL is `dock_cradle_v12.stl`.

**Fitting the plates:**
1. Tin a spot on the copper face, about 3 mm below the plate's top edge and centred. Solder ≥ 18 AWG wire there.
2. Slide the plate down into its slot, copper facing out, until it sits on the bottom.
3. Lay the wire in the groove and push it down the Ø4 hole into the hollow.

The plate's top edge then sits 4.6 mm below the cradle top. The lips hold it against the pins' push, and gravity holds it down.

**Polarity:** as in log 032. Dock jack + → switch (COM → NO) → right plate. Jack − → left plate.

## The robot doesn't dock far enough: the stop pads (v13, 2026-10-29)

**The user's report, on the printed v12 cradle:** "those squares" stop the robot before its pogo pins reach the plates. **They are the two stop pads** (±38°, r 125.86, about 5 mm proud of the face).

**My misread first:**
- I took the report to mean the inner lip rails beside the jack pocket and cut them out of the model (v13).
- Model margins, measured from the parked position (pads touching):

  | Part | Touches the back cover after |
  |---|---|
  | Stop pads | 0.7 mm |
  | Inner rails (v12) | 3.1 mm |
  | Plates and lips | 6.3 mm |

- So the rails don't touch first. They only would if the pads come down by more than about 2.4 mm.
- **v13 is kept**, since the pads will probably come down. The rails weren't needed anyway (the pins push the plates into their slots).

**Why the pins don't reach:**
- In the model, the pins compress about 1.3 mm with the shell on the pads.
- On the real robot they fall short, so something differs from the model. Candidates: the real pin protrusion, or where the back cover sits on the robot.
- Not measured yet.

**Fix on the printed cradle, no reprint:**
1. Measure the gap between the pin tips and the plates with the robot resting on the pads.
2. Shave both pads equally by that gap + about 1.5 mm. There's about 5 mm of pad to work with.
3. Check that the KW11 lever still clicks and isn't crushed.
4. If the pads come down more than about 2.4 mm, cut the inner rails flush too, and glue the plates' inner edges.

**Supports:** the pads were the overhangs that needed PETG-interface supports (26 swaps). Giving them a 45° underside would have printed them with none. Do that when the pads are updated with the measured shave.

## Stop pads removed (v14, 2026-10-29)

**The user's measurement:**
- With the robot resting on the pads, the gap between the pin tips and the plates equals the pads' height (about 5 mm).
- With the cradle turned upside down, so the pads no longer meet the robot, the pins touch the plates.

So the pads have to go completely.

**What this means:**
- The real robot meets the pads about 5 mm earlier than the model.
- **The robot now stops on the pins** (and the jack in its pocket), not on a hard stop. The docking routine has to drive in slowly and stop as soon as charging is detected.
- Checks after shaving:
  - the KW11 lever clicks but isn't crushed;
  - the jack doesn't bottom in its 6 mm pocket (the model leaves about 1 mm at 5 mm deeper).

**`charging-dock-v1` v14:**
- The pads are cut back to the r 131 face (3.7 cm³); nothing stands proud of the face now.
- The floating check (upside down) leaves only bridges, so the cradle plate drops supports, PETG and the prime tower: **7 h 57 min, 304 g PLA, 0 swaps**.
- `dock_cradle_v14.stl` replaces `~/Downloads/gerdoo_dock_cradle_A1.3mf`.

**On the printed v12 cradle:** shave both pads flush with the curved face.

## Still open

- **`gerdoo-assembly-preview`** still links dock v10. Update its references next time it's opened.
- **Letter colour:** white suggested, for contrast with the black body. The diffuser must be white or translucent.
