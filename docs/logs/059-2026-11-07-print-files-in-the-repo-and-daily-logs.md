# 059 — Print files in the repo, and logs written every day

| | |
|---|---|
| **Date** | 2026-11-07 |
| **Type** | Design decision (repo) |
| **Status** | ✅ `print/`: 16 final plates (3MF), 41 per-part STLs, guide · ✅ `sim/web/tools/export_print_stls.py` · ✅ Logs 048–058 back-filled for 2026-10-21 → 11-07 · ✅ Logs 042, 045, 046 corrected |
| **Severity** | — |

---

## The request

"make sure all the things we experienced so far are in the logs on a daily basis, also, keep the stl files and 3mf files for printing with a guide in the repo"

## Logs were 9 days behind

The last log was 047 (2026-10-29), but work had gone on through 10-30 and 11-05 → 11-07, and some 10-21 → 10-28 topics never made it in. Two agents read the session transcripts per day and listed what wasn't logged; logs 048–058 were written from that, in date order:

| Log | Day | Topic |
|---|---|---|
| 048 | 10-21 | Threaded M3 spacers; the common-ground plan |
| 049 | 10-23 | Ultrasonic beams graze the covers; the 2.1 vs 2.5 DC plug |
| 050 | 10-25 | Charge-path diodes; board wiring; log 042's topple was the neck |
| 051 | 10-26 | Motor-driver wiring; the 30 A fuse on the servo feed |
| 052 | 10-27 | A motor spun with the Teensy unplugged |
| 053 | 10-29 | Light card; motor torque; Jetson power drops; reSpeaker gone |
| 054 | 10-30 | reSpeaker back; neck servos on the bus |
| 055 | 11-05 | Voltage sensor 0 V; motor pack not charging; reversed battery kills the step-down |
| 056 | 11-06 | New step-down; charging proven; the 45 W supply overload; Jetson drained |
| 057 | 11-06 | 2nd floor health check; camera paths; arm sides relabelled (0.5.1) |
| 058 | 11-07 | The step-down's current limit bypassed by the shared ground; new charger |

**Corrections to older logs:**
- 042's "second topple" section is marked as a misunderstanding (it was the neck).
- 045's dock sign has its normal-support slice.
- 046's reference to the beam clash now points at 049.
- 011's 30SQ050 rating is fixed (3 A, not 30 A).

**From now on:** each working day's events get logged that day.

## Print files

**Before:**
- Work files lived in the git-ignored `build/print/` (227 MB of every iteration).
- Finished plates were copied to `~/Downloads`.
- Nothing printable was in the repo.

**Now, `print/`:**
- `print/3mf/`: the **final** Bambu A1 plate of each part group, 16 files, 9.6 MB. They're the newest `~/Downloads` copies, each checked by its embedded plate title against the newer files in `build/print/`.
  - **Two plates carry superseded parts:**
    - the 3rd floor plate has LDR cradle v6 (v7 is on the back-cover plate);
    - the back-cover plate has display retainer v10 (v13 is its own plate).
  - Both 3MFs are kept as they were; `print/README.md` says to delete those parts before slicing, and they're left out of `stl/`.
- `print/stl/NN-name/`: one STL per part, 41 files, 35 MB. They're **cut from the final 3MFs**, so each is in its print orientation, on Z = 0, with fins included. Duplicates are stored once (e.g. `separator-hex-77` ×4).
  - The M3 spacer's source STL was lost with an old session scratchpad (log 048); its 3MF was the only copy, which is why the STLs are cut from the 3MFs rather than taken from `build/print/`.
- `print/README.md`: the guide. It covers:
  - printer and AMS slots (black PLA, PETG interface only);
  - preset-name pitfalls;
  - normal, not tree, supports;
  - M3 Ø4.4 / M2 Ø3.2 inserts;
  - a row per plate with parts and counts, the re-sliced time, grams and swaps, orientation notes and the log link.

**Privacy:** every 3MF was scanned for paths, user names, e-mails, printer serials and Bambu account IDs. There were none: they were all written by our own scripts.

**Not included:**
- The ElRobot arm files (upstream project, linked from the guide).
- Superseded iterations (base-board holders v1, the PLA-supports-only 1st layer, the standalone antenna bracket v1, the combined covers plate).

## `sim/web/tools/export_print_stls.py`

```sh
python3 sim/web/tools/export_print_stls.py <plate.3mf> <outdir> [--skip "<object name>"]
```

- Reads the 3MF's build items and components and applies their transforms. It keeps only `normal_part` volumes, dropping support enforcers and modifiers.
- Writes one binary STL per object, centred in X/Y and resting on Z = 0.
- Names come from the object name up to its first " (". Identical parts are found with rotation-free numbers (triangles, area, volume, height), so a hex separator turned on the plate still counts as a copy.

**Re-slice:** all 16 plates sliced headless with Bambu Studio 2.8.02 (`--slice 0`), all "Success.", no warnings. The times are in the guide.

## Takeaways

- Keep finished print files in the repo next to the logs that explain them. Scratchpads and Downloads folders get lost.
- A daily log costs minutes. Reconstructing nine days from transcripts cost two agents and an hour.
