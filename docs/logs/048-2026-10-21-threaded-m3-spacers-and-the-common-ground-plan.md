# 048 — Threaded M3 spacers, and the common-ground plan

| | |
|---|---|
| **Date** | 2026-10-21 |
| **Type** | Print + design decision |
| **Status** | ✅ Spacer v3 sliced (`print/3mf/gerdoo_m3_spacers_A1.3mf`) · ⏳ v3 fit not reported · ✅ Ground plan recorded in `inventory.md` · ⚠️ Not fully wired (see log 058) |
| **Severity** | — |

---

Written on 2026-11-07 from the session transcript. Neither topic made it into a log on the day.

## 1. Twelve printed M3 spacers

**The request:** the user sent two caliper photos of a white nylon M3 hex standoff (10.0 mm long, 5.2 mm across flats) and asked for "a plate to print 12 of these with threads for a m3". What they're for wasn't said.

| Version | Geometry | Slice | Result |
|---|---|---|---|
| v1 | 5.2 AF × 10 mm, plain Ø2.6 pilot for a self-tapping M3. An M3 heat-set insert won't fit: it would leave a 0.4 mm wall | 49 min, 3.1 g | **Printed, failed:** "near impossible to screw in and there was no threads, make a little bit bigger and height at 7mm" |
| v2 | Ø2.9 pilot, 0.3 mm entry chamfers, 7 mm | 21 min, 1.9 g | Replaced a minute later, never printed |
| **v3** | **Modelled ISO M3 × 0.5 internal thread, +0.10 mm radial clearance** (major Ø3.20, minor Ø2.66), 45° lead-ins at both ends, 5.2 AF × 7 mm. 25,632 triangles, no non-manifold edges | **46 min, 1.9 g** (0.08 mm layers, 4 walls, outer wall 60 mm/s, 3 mm brim) | Sliced. **No fit report yet** |

- **Plate:** 12 on a 4 × 3 grid at 20 mm pitch. Spec: `sim/web/tools/plate_m3_spacers.json`.
- **Lost source:** the v3 STL and its generator script lived only in that session's scratchpad. The 3MF is the only copy of the geometry. It's now in `print/3mf/`, and `print/stl/05-m3-spacers/` was cut back out of it.
- **If v3 doesn't fit:** 0.15 mm clearance if it's too tight, 0.05 if it wobbles.

**Wrong turn:** v1 relied on a self-tapping screw cutting PLA in a 0.4 mm wall. A printed thread, with clearance and a fine layer height, is the fix for such a small part.

## 2. Common ground and the star point

Recorded in `inventory.md` ("Grounding — the actual failure mode") that day; only now in a log.

- **Motors and servos** take + through their fuse and − straight back to the **power pack's P−**, as a pair. They pass through no board.
- **Small returns** (about 8 A in all) go to a **10 A screw-terminal ground board**, fed by 16 AWG from the electronics pack's P−:
  - the UPS input, ~2.1 A;
  - the XL4015 charge return, ~2 A;
  - the MINI560 / LM2596S inputs, ~2 A;
  - the hub, ~1 A;
  - the XVF3800, ~0.8 A;
  - the Teensy's own spur and the sensors.
- **A 16 AWG link between the two packs' P−** is the common ground. It carries almost nothing; it holds both 0 V levels together.
- **Rules:**
  - Ground at the BMS **P−**, never B− or a cell negative.
  - The LED strip's − goes only to the D4184's OUT−.
  - Join negatives only, never the two packs' + leads.

**Later consequence (log 058):** the XL4015 senses its charge current with a resistor between its IN− and OUT−. Any shared ground in parallel with that resistor bypasses it, so on this robot the XL4015's current limit cannot work. The plan above makes that path even stiffer. The charger is being replaced with one that senses on the + side.

## Takeaways

- Printed threads at 0.08 mm with ~0.1 mm clearance work where a pilot hole for a self-tapper doesn't.
- Keep any generated geometry somewhere that outlives the session: `build/print/` for work in progress, `print/` once final.
