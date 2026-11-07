# 043 — Holders for the 1st-floor boards: power-board plates, a charger table and a front tower

| | |
|---|---|
| **Date** | 2026-10-21 |
| **Type** | Design + print setup |
| **Status** | ✅ Designed with the user over a few rounds, clash-checked, in `gerdoo-assembly-preview` v39 · ✅ `gerdoo_base_board_holders_A1.3mf`: 2 h 38 min, 40 g PLA, no supports · ⏳ Not printed |
| **Severity** | Medium: half the base boards (servo board, MOSFET, both power boards, charger) had nowhere to mount |

---

Follows [029](029-2026-10-16-arm-mounts-on-the-first-layer.md) (the fit study's "4 vertical holders", never built) and [042](042-2026-10-21-covers-print-failed-groove-retainer-louvers-fins.md).

## The problem

**The user's catch:** the D4184 MOSFET board, the servo board and the two power distribution boards (Evemodel PCB007, 95 × 18.7 mm) had no place.
- Log 029 only put placeholders in the preview.
- The printed 1st layer has no holes for them.
- **Rule from the user:** nothing may crowd the battery's front face, which is where its outputs are.

## How the layout was reached

1. **The user's idea:** upright panels left and right of the battery, held down by a thin foot under the battery.
   - **Problem:** the PCB007 is 95 mm. Upright it's taller than the 77 mm under the 2nd floor, and beside the battery there is only 58 mm before the rear hex post.
2. **Laid flat** (the user: "horizontally it should fit"), running front to back from just in front of the rear hex post to past the battery's front corner, it fits. This is the final layout.
3. **A tower in front of the battery** for the other boards: rejected, because that is the battery's output side.
4. **Next to the Teensy:** the 20 mm gaps either side of it are its wiring channels, since its terminal rows face the drivers, and its USB end faces the battery. The user chose the **space in front of the Teensy**.
5. **The charger:** about 22 mm deep with its heatsink, so it doesn't fit in front of the Teensy.
   - **My wrong turn:** I put it on top of the battery before the user had answered whether that space was free. It isn't.
   - **The user's idea:** a table raised over the 38 × 38 mm centre hole.

## The parts (`Base-board holders v1` in the preview, preview coordinates)

**No new holes in the deck.** Everything locates on the posts: rings dropped over them with the 2nd floor off, plus the feet under the battery.

### Side plates ×2, one per power board
- **Base:** a 1.6 mm strip at x ±56.5…76.5, z −81…20, and a **1.2 mm foot under the battery's side edge**.
- **Rings:** one round the middle round post (Ø16, ring 16.5/21) and a C-ring round the rear hex post, open toward the battery.
  - The robot-right hex post is right against the battery, so its ring can't close.
  - The two plates differ only at the back: the rear hex posts sit at x +65 and −60.
- **Holding the board, with no screws:**
  - supports under its bare ends;
  - a centre rib between the two pin rows;
  - a **hook** over the back end and a **snap latch** over the front end (1.2 × 8 mm, 0.6 mm lip);
  - edge guides.
- **To fit a board:** slide the back end under the hook, then press the front end down past the latch.
- **Board position:** z −77…18, which leaves 2 mm to the hex post and 7 mm to the motor driver.

### Charger table
- **Top:** 74 × 41 × 2.5 mm, 38 mm above the deck, between the round posts. It covers the centre hole, the battery's outputs and the Teensy's USB end, all of which pass under it.
- **Rings:** round both round posts, level with the top.
- **Front legs:** two, standing just behind the Teensy board's back edge.
- **Holes:** a cable slot at the back edge, and 4 zip-tie slots for the XL4015, which lies flat with its heatsink up and 18 mm left under the 2nd floor.
- **Printing:** upside down, so the top and rings are on the bed.

### Front tower
- **Wall:** 46 × 72 × 2.5 mm, just in front of the Teensy board's front end, between the two front cable slots.
- **Base:** a flange, plus bars to **rings round the two front hex posts**.
- **Front face:**
  - **servo board:** 4 Ø6.5 bosses with **M2 heat-set inserts (Ø3.2 × 4.5)** on Waveshare's 37 × 28 pattern;
  - **D4184 and MINI560:** side by side underneath, on 2 mm spacer ribs, each held by zip ties through slots in the wall.
- **Back face:** the voltage sensor, on a ledge with one zip tie.
- **Clearances:** the servo board's tallest parts are about 1.7 mm from the chest cover's inside at its corners. The light boards sit behind the chevron louvers, so they get the airflow.

### Checks
- **Clash check against the preview** (deck, posts, all 1st-floor electronics, the arm bases, both covers, the 2nd floor). The only overlaps are planned: the feet under the battery placeholder (674 / 636 mm³).
- **The first tower clashed with the front hex posts** (106 mm³ each): its bars ran into the post centres. They were trimmed at the rings, and the overlap is now 0.04 mm³.
- **Floating check:** the remaining spots are the bosses' undersides, the insert-hole and tie-slot tops (≤ 3.5 mm), and the 2 mm and 0.6 mm lips on the hook and latch.

## Print file

**`~/Downloads/gerdoo_base_board_holders_A1.3mf`** (spec `sim/web/tools/plate_base_board_holders.json`):
- side plates flat;
- table upside down;
- tower standing;
- 4 mm brim, no supports;
- **2 h 38 min, 40.2 g**, no warnings.

## Hardware

- **Servo board:** 4 × M2 heat-set inserts, 4 × M2×6 (its holes are M2.5, so add washers).
- **Zip ties, about 2.5 mm wide:**
  - 4 for the D4184 / MINI560, at two heights through the left, centre and right slots;
  - 1 for the voltage sensor;
  - 2 for the charger.
- **Power boards:** nothing; the hook and latch hold them.

## Assumed, not measured

- **D4184 (33 × 18), MINI560 (29 × 18), voltage sensor (27 × 13), XL4015 (52 × 27 × 18):** the zip ties take a few mm either way.
- **PCB007:** 95 mm long. If it is longer, the latch won't close; shave the latch lip.
- **Battery holder:** still the listing size. The feet assume it sits flat on the deck.

## The superseded fit study

Log 029's placeholder boards and "vertical holders" are hidden in the preview's `Fit study`. They are superseded by this layout.
