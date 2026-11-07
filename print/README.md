# Print files

Every printed part of Gerdoo, ready to print. Two forms of each:

- **`3mf/`**: the Bambu Studio project for each plate, set up for a **Bambu Lab A1**: parts placed, oriented, supports painted, settings tuned. Open it and print.
- **`stl/`**: one STL per part, already turned to its print orientation, resting on Z = 0. Use these on another printer or slicer. A part printed more than once is stored once; the tables below give the count.

These are the final versions. Earlier iterations, and why each one changed, are in the logs linked per plate. Work in progress (new exports, test slices) stays in the git-ignored `build/print/`; a plate is copied here once it is final.

## Printer and materials

| | |
|---|---|
| Printer | Bambu Lab A1, 0.4 mm nozzle, textured PEI plate, bed 60 °C |
| AMS slot 1 | **Black PLA**: Polymaker PolyLite PLA Pro, preset `PolyLite PLA @BBL A1`. The whole robot is black |
| AMS slot 2 | **PETG, support interfaces only**, preset `Generic PETG @BBL A1 - Support` (a user preset: `Generic PETG @BBL A1` saved under that name). PETG doesn't bond to PLA, so the interface needs no gap and peels off clean |
| Process | `0.16mm High Quality @BBL A1` plus per-plate overrides stored in the 3MF |

**Before printing a 3MF:**
- **The preset names must exist in your Bambu Studio.** If one is missing, the GUI silently drops the plate's settings and falls back to stock, even though the file is fine. Create the PETG preset above first.
- **Supports are "normal (manual)"** and only where painted. Tree supports toppled at the first PETG layer on earlier plates (logs 036, 045).
- **Don't swap the PETG interface for PLA supports** to save time. PLA-on-PLA supports cost an hour of peeling and scar the surface.
- No plate has room for a prime tower; the A1 purges into its chute.

**Hardware that goes into the prints:**
- **M3 heat-set inserts in every Ø4.4 hole** (through the plate, or 7 mm deep blind). **M2 inserts in the Ø3.2 holes.**
- Everything is screwed (M3 or M2 only, no M4); there are no snap fits or zip-tie slots.
- Each floor has a 20 mm grid of spare M3 insert points for later mounts.

## Robot body

Listed in build order. *Time* is Bambu Studio's estimate for the whole plate (re-sliced 2026-11-07 with Bambu Studio 2.8.02); swaps are PLA↔PETG filament changes; no figure means PLA only, no swaps.

| # | Plate (3MF) | Parts (STL, count) | Time · filament · swaps | Notes | Log |
|---|---|---|---|---|---|
| 01 | [`gerdoo_1st_layer_A1_v5.3mf`](3mf/gerdoo_1st_layer_A1_v5.3mf) | `1st-layer-v5` | 19 h 22 min · 327 g PLA + 24 g PETG · 168 swaps | The base plate, printed **deck-top face down**. Supports only under the four ultrasonic pods, with a PETG interface. This file still has tree supports; set them to normal (manual) if you reprint it. 250 mm wide: 3 mm spare each side on the A1 | [033](../docs/logs/033-2026-10-17-printing-the-1st-layer-on-the-a1.md) |
| 02 | [`gerdoo_arm_bases_separators_A1_v2.3mf`](3mf/gerdoo_arm_bases_separators_A1_v2.3mf) | `arm-base-l`, `arm-base-r`, `separator-hex-77` ×4, `separator-round-80` ×2 | 21 h 56 min · 377 g + 11 g PETG · 20 swaps | Arm bases upright; a 45° draft under each neck leaves only the disc's underside to support (PETG interface). Separators carry the 2nd floor | [036](../docs/logs/036-2026-10-18-arm-bases-and-separators-print.md) |
| 03 | [`gerdoo_motor_shims_A1.3mf`](3mf/gerdoo_motor_shims_A1.3mf) | `motor-bracket-shim-0-68/1-00/1-48/1-96-mm` ×2 each | 49 min · 20 g | Only if the drive wheels slip: a shim under each motor bracket lowers the wheel. Pick the thickness by test | [040](../docs/logs/040-2026-10-20-drive-wheels-lost-grip-on-the-new-1st-layer.md) |
| 04 | [`gerdoo_base_board_holders_v5_A1.3mf`](3mf/gerdoo_base_board_holders_v5_A1.3mf) | `side-wall-robot-left`, `side-wall-robot-right`, `servo-tower`, `teensy-washer` ×2 | 3 h 41 min · 67 g + 0.3 g PETG · 2 swaps | Walls beside the battery for the power, light and charger boards, clamped under the motor-driver standoffs. Servo tower's ears supported (PETG interface) | [044](../docs/logs/044-2026-10-22-base-board-holders-v2-screwed-walls.md) |
| 05 | [`gerdoo_m3_spacers_A1.3mf`](3mf/gerdoo_m3_spacers_A1.3mf) | `m3-threaded-hex-spacer` ×12 | 39 min · 2 g | 5.2 mm hex × 7 mm with a modelled M3 thread (+0.1 mm clearance), at 0.08 mm layers. Fit not yet reported: if tight, regenerate at 0.15 clearance | [048](../docs/logs/048-2026-10-21-threaded-m3-spacers-and-the-common-ground-plan.md) |
| 06 | [`gerdoo_2nd_floor_A1.3mf`](3mf/gerdoo_2nd_floor_A1.3mf) | `2nd-floor-v2`, `2nd-3rd-separator` ×4, `hub-rear-spacer` ×2 | 11 h 57 min · 240 g | Printed as mounted, PLA only (two Ø17 bridges, no supports) | [038](../docs/logs/038-2026-10-19-printing-the-2nd-floor.md) |
| 07 | [`gerdoo_3rd_floor_A1.3mf`](3mf/gerdoo_3rd_floor_A1.3mf) | `3rd-floor-v2`, `speaker-grille-cap`, `antenna-bracket-back-v2`, `dht22-rail-mount-v2` | 9 h 42 min · 178 g | PLA only. **The plate also carries LDR cradle v6, superseded by v7 on plate 10: delete it before slicing** (it's left out of `stl/`) | [039](../docs/logs/039-2026-10-20-3rd-floor-cable-slot-and-extension-grid.md) |
| 08 | [`gerdoo_neck_lidar_v3_A1.3mf`](3mf/gerdoo_neck_lidar_v3_A1.3mf) | `neck-pan-base`, `neck-pan-clamp`, `neck-arm`, `neck-head-yoke`, `lidar-holder-v2` | 6 h 48 min · 100 g + 0.6 g PETG · 2 swaps | The STS3215 neck and the C1 lidar holder. The yoke prints on its back with a supported pad (PETG interface) | [035](../docs/logs/035-2026-10-17-sts3215-neck-and-taller-lidar.md) |
| 09 | [`gerdoo_front_cover_v7_A1.3mf`](3mf/gerdoo_front_cover_v7_A1.3mf) | `front-cover-v12` | 10 h 36 min · 145 g | **Standing, on its own plate**, with snap-off stabiliser fins (part of the STL) and an 8 mm brim: an earlier cover toppled mid-print. Snap the fins off after | [041](../docs/logs/041-2026-10-20-front-cover-printable-inlays-and-display-plug.md), [042](../docs/logs/042-2026-10-21-covers-print-failed-groove-retainer-louvers-fins.md) |
| 10 | [`gerdoo_back_cover_v6_A1.3mf`](3mf/gerdoo_back_cover_v6_A1.3mf) | `back-cover-v11`, `ldr-cradle-v7` | 5 h 48 min · 86 g | Same as the front: standing, fins, brim. **The plate also carries an older display retainer (v10): delete it and print plate 11 instead** | [042](../docs/logs/042-2026-10-21-covers-print-failed-groove-retainer-louvers-fins.md) |
| 11 | [`gerdoo_display_retainer_A1.3mf`](3mf/gerdoo_display_retainer_A1.3mf) | `display-retainer` (v13) | 7 min · 2 g | Holds the reactor LCD behind the front cover. Flat, 100 % infill. v13 joins the screw ears to the frame | [042](../docs/logs/042-2026-10-21-covers-print-failed-groove-retainer-louvers-fins.md), [053](../docs/logs/053-2026-10-29-light-card-motor-torque-jetson-power-drops-respeaker-gone.md) |
| 12 | [`gerdoo_coil_pads_A1.3mf`](3mf/gerdoo_coil_pads_A1.3mf) | `coil-pad` ×12 | 4 min · 1 g | Inlays for the front cover's 12 pockets. Print in **silk** (tri-colour). Press in, a drop of CA glue if loose | [041](../docs/logs/041-2026-10-20-front-cover-printable-inlays-and-display-plug.md) |
| 13 | [`gerdoo_gold_ring_A1.3mf`](3mf/gerdoo_gold_ring_A1.3mf) | `gold-ring-inlay` | 9 min · 4 g | The reactor ring, ID 77.5 / OD 86 / 3 mm. Print in **gold** | [041](../docs/logs/041-2026-10-20-front-cover-printable-inlays-and-display-plug.md) |

## Charging dock

| # | Plate (3MF) | Parts (STL, count) | Time · filament · swaps | Notes | Log |
|---|---|---|---|---|---|
| 14 | [`gerdoo_dock_cradle_A1.3mf`](3mf/gerdoo_dock_cradle_A1.3mf) | `dock-cradle-v14` | 7 h 50 min · 304 g | **Upside down**: top on the plate, cavity open upwards, no supports. Big blocky part, so 0.20 mm, 3 walls and lightning infill (the HQ defaults made it 64 h) | [045](../docs/logs/045-2026-10-28-printing-the-dock.md) |
| 15 | [`gerdoo_dock_sign_A1.3mf`](3mf/gerdoo_dock_sign_A1.3mf) | `sign-mast`, `sign-head` | 12 h 8 min · 368 g + 1.6 g PETG · 8 swaps | Mast standing on its foot flange; head on its side with 3 small painted **normal** supports (PETG interface). 0.20 mm, lightning infill. The mast screws onto the cradle with 4 × M3 into Ø4.4 inserts | [045](../docs/logs/045-2026-10-28-printing-the-dock.md) |
| 16 | [`gerdoo_dock_letters_A1.3mf`](3mf/gerdoo_dock_letters_A1.3mf) | `letter-1-e`, `letter-o` ×2, `letter-4-d`, `letter-5-r`, `letter-6-g`, `light-line-diffuser` | 20 min · 7 g | Print in **white** (the diffuser must be white or translucent). Letters face down. The 3MF applies **XY −0.08 mm** so they press into their 0.6 mm recesses; set that yourself when printing the STLs | [045](../docs/logs/045-2026-10-28-printing-the-dock.md) |

## Not in this folder

- **The two ElRobot arms** are printed from the upstream project: [norma-core/hardware/elrobot](https://github.com/norma-core/norma-core/tree/main/hardware/elrobot). Our arm bases (plate 02) replace its table clamp.

## Regenerating the files

- The 3MFs were built from Fusion exports by `sim/web/tools/make_plate_3mf.py` (plate specs `sim/web/tools/plate_*.json`) and, for the 1st layer, `make_print_3mf.py`.
- The STLs are cut from the final 3MFs by `sim/web/tools/export_print_stls.py`:
  ```sh
  python3 sim/web/tools/export_print_stls.py print/3mf/<plate>.3mf print/stl/<NN-name> [--skip "<object name>"]
  ```
- Check a 3MF headless: `BambuStudio --slice 0 --outputdir <dir> <file.3mf>`, then read `<dir>/result.json`.
