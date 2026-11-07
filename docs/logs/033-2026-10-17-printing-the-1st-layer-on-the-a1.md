# 033 — Printing the 1st layer on the A1

| | |
|---|---|
| **Date** | 2026-10-17 |
| **Type** | Print setup for one part |
| **Status** | ✅ The project file slices cleanly in Bambu Studio 2.8.02.61 · ⏳ Not printed yet |
| **Severity** | Low |

---

Follows [032](032-2026-10-17-measurements-dock-sign-and-arm-mount-angle.md).

## What was asked

A print-ready Bambu A1 project for the 1st (bottom) layer, `1st-layer-v4`.
- **Filaments:** PLA (black) for the part, with the last layers of support in PETG. That peeled easily when the arms were printed. The PLA was SUNLU Hyper PLA at first; from v4 it's **Polymaker PolyLite PLA Pro**.
- **Priority:** quality first.
- **Reference:** use best practice, not the user's earlier print settings.

## The files

They are in `~/Downloads`. Neither is committed: each is a 3.8 MB mesh.

| File | Supports | Time | Filament | Swaps |
|---|---|---|---|---|
| `gerdoo_1st_layer_A1_v5.3mf` | PLA trees, PETG top interface | 22 h 45 min | 314 g PLA + 11 g PETG (+ flush) | 168 |
| `gerdoo_1st_layer_A1_PLA-supports-only_v5.3mf` | PLA trees, stock 0.16 mm gap | 17 h 35 min | 317 g PLA | 0 |

- **v3 onward:** the 4-pod plate ([034](034-2026-10-17-four-ultrasonic-sensors.md)).
- **v4:** set up for PolyLite PLA Pro.
- **v5:** set up for the user's black High Speed Matte PETG.
- **Older numbers:** v1 and v2 had 3 pods, and the timing notes further down are from them.

- **Builder:** `sim/web/tools/make_print_3mf.py`, run on a fresh STL export. To rebuild the files:
  `python3 make_print_3mf.py first_layer.stl pods.json <outdir> [--pla-supports]`
- **Mesh:** exported from Fusion at 0.02 mm surface deviation and 2° normal deviation, which gives 394,528 triangles. The "High" preset is 10°, which leaves 0.48 mm flats on the r125 edge.
- **Template:** the project settings come from one of the user's own A1 projects (`down-panel.3mf`). So the printer, plate and AMS fields are the ones Bambu Studio writes itself, and only the process and filament values below are changed.

## Settings and why

**Orientation**
- **Deck top down on the Textured PEI plate.** It's the only big flat face. The pods, casters and motor pockets then all point up.
- **Rotated 90°**, so the back pod sits at the bed's left edge. That keeps the pod's supports off the A1's purge line at Y 0–1.

**Process** (based on 0.16 mm High Quality @BBL A1)

| Setting | Value | Why |
|---|---|---|
| Layer height | 0.16 mm | Smoother curved edges and pods than 0.20 |
| Walls | 4, Arachne | Insert holes and bolt bosses sit in solid wall, not infill |
| Top / bottom shells | 6 / 5 | No infill showing through on the deck |
| Infill | 25 % gyroid | Stiff in every direction for a 250 mm disc, and stays quiet |
| Elephant-foot compensation | 0.12 mm | The deck's bottom edge and hole rims stay true |
| Seam | aligned | One clean seam line instead of scattered zits |
| Brim | none | Textured PEI holds PLA, and a brim would mark the rounded edge |
| Prime tower | off | It doesn't fit: the part covers 250 × 235 of the 256 bed. The A1 purges into its chute. |

**Supports**
- **Type:** organic trees, enforcers only (`tree(manual)`).
- **Where:** support enforcer boxes around the ultrasonic pods: 3 in v1–v2, 4 in v3 (log 034). Nothing else on the plate needs support.
- **Threshold:** 50°.

**PETG interface** (`gerdoo_1st_layer_A1.3mf` only)

| Setting | Value |
|---|---|
| Top interface | 2 layers PETG, 0 mm Z gap |
| Interface spacing | 0 (solid) |
| Interface pattern | rectilinear interlaced |
| `support_interface_not_for_body` | on |
| Bottom interface | none: tree feet stand on PLA with a 0.16 mm gap |
| Flush | 170 mm³ each way |

**Filaments**
- **Slot 1, PolyLite PLA Pro:** Bambu has no PLA Pro profile, so this starts from Bambu's **PolyLite PLA @BBL A1** (same maker, flow 0.95).
  - **Temperatures:** 215 °C, 220 °C for the first layer. The box says 190–220.
  - **Bed:** 60 °C on textured PEI. That's the top of the box's 30–60, where Bambu's PLA profiles use 65.
  - **Speed:** flow capped at 12 mm³/s, about 165 mm/s for inner walls and infill. The box says 30–70 mm/s, and outer walls stay at 60.
  - **v1–v3:** stock Generic PLA High Speed (220 °C, 65 °C), for SUNLU Hyper PLA.
- **Slot 2, PETG:** the user's own preset "Generic PETG @BBL A1 - Support": Generic PETG at 255 °C with every plate type at 65 °C. In v4 its textured-plate value is 60, to agree with the PLA. It never touches the bed.
  - **v5, for the user's spool:** black High Speed Matte PETG.
    - **Label:** 230–240 °C at 50–100 mm/s, bed 70–80 °C, spool good to 70 °C.
    - **Nozzle: 240 °C.** Interface prints in that slow band, and cooler PETG bonds less to the PLA.
    - **Bed: 60.** The PETG never reaches the bed, and 70+ would soften the PLA disc's bottom.
    - **Swaps:** Bambu heats to 270 °C (the PETG range top) for each purge into the chute. That's normal.
    - **Drying:** 65 °C at most, because of the spool's 70 °C rating.

## Wrong turns

- **Bambu Studio 2.4.0.70 crashed on every CLI slice**, in `PartPlateList::set_shapes`. After the user upgraded to 2.8.02.61, the same file sliced.
- **2.8 errors with -104 "G-code outside printable area".** Its prime tower is about 55 × 56 mm with ribs and has nowhere to go. Turning it off and rotating the plate 90° fixed it.
- **A flattened, non-inheriting preset gave "process not compatible with printer".** Presets have to `inherits` a system profile and list only their differences.
- **`--export-3mf` fails from the CLI** ("Failed exporting 3mf files"), even though the slice succeeds. So the delivered files are unsliced projects. Slice them in the GUI.
- **First PETG version: 21 h 19 min and 231 min of flushing.** It used PETG interface top and bottom and flushed 280 mm³.
  - Two changes: no bottom interface, and a 170 mm³ flush.
  - Result: 20 h 27 min and 191 min of flushing.
  - **The swap count stayed at 168.** The pods' holes and bosses are curves, so each layer up a curve has new overhang that needs interface. That's 84 layers × 2 swaps.

- **v1 opened in the Bambu Studio GUI with stock settings and no supports.**
  - What the user saw: process "0.16mm High Quality @BBL A1", 219 g, 9 h 22 min, 0 swaps, and a "floating cantilever … enable support" warning. Every change was dropped.
  - Root cause: v1 named its presets "Gerdoo base 0.16 HQ …", "SUNLU Hyper PLA … (gerdoo)" and so on. The GUI only applies a project's settings when the preset names exist on the machine. Otherwise it falls back to stock presets. The CLI applies the values whatever the names, which is why the CLI slice had supports.
  - Fix: name presets the way the GUI saves its own projects (the user's `Lightbox Draft` 3MF shows the pattern). Use a system or user preset name that exists, and list the changed keys in `different_settings_to_system`. The GUI then opens them as unsaved changes on that preset.
  - Lesson: a CLI slice is not proof the GUI will load the file the same way.

## Changes to the model for printing

- **The Teensy breakout's printed standoffs are off** (suppressed `TeensyStandoffs`). They sat on the deck top, which is now the face on the bed.
- **In their place:** Ø3.2 × 5 mm holes for M2 heat-set inserts in the flat deck (`tb_insert_extra` = 5), plus M2 brass standoffs.

## Takeaways

- **PETG interface costs about 4.7 h here,** almost all of it filament swaps. It buys easy, clean removal inside the sensor holes. Those surfaces end up hidden behind the HC-SR04 cans.
- **To drop the swaps, make the pods self-supporting.** Pointed (teardrop) hole tops and chamfered boss undersides would need no support at all. That's a model change, not done yet.
- **Bambu CLI** (2.8.02.61): `BambuStudio --slice 0 --outputdir <dir> <file.3mf>` writes `plate_1.gcode` and `result.json`. The JSON has the time, grams, swap count and per-feature times, so a file can be checked without opening the GUI.

## Outcome (2026-10-18): the PLA-only file was the wrong call

**What happened:** the user printed `gerdoo_1st_layer_A1_PLA-supports-only_v5.3mf`, on my recommendation. Removing the supports took **almost an hour** and **scratched the surface a lot**.

**Why my reasoning was wrong:**
- I argued that the supported surfaces would mostly be hidden (inside the can holes, the undersides of the pods), so the PETG interface "bought almost nothing you'll see".
- I discounted the removal itself. Organic PLA trees with a 0.16 mm gap fuse to the curved pod surfaces. Prying them off scuffs the visible walls next to them, and the user had said quality came first.

**Rule from now on:** supported prints use the **PETG interface by default**. That's 2 layers of the user's black High Speed Matte PETG at 240 °C with zero gap, as in `gerdoo_1st_layer_A1_v5.3mf`. All-PLA supports are only offered as an explicit opt-in, never recommended to save time or filament swaps.

**Repairing the print:**
- A heat-gun pass on low turns white scuff marks black again.
- Wet-sand 400 → 800 → 1500 grit for deeper scratches.
- Test-fit an HC-SR04 can in each hole and scrape off any ridges (0.3 mm clearance).
