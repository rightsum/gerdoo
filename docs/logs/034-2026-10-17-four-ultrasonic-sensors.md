# 034 — Four ultrasonic sensors: the back pod couldn't take its sensor

| | |
|---|---|
| **Date** | 2026-10-17 |
| **Type** | Design fix (found by the user) |
| **Status** | ✅ `1st-layer-v4` v11 has 4 pods, 2 at each end · ✅ All 4 sensors checked to slide in · ✅ Preview updated and saved · ✅ Print files rebuilt (log 033) · ✅ Simulator updated, and its lidar now sees the dock's sign |
| **Severity** | High for the print: the old back pod could never have held its sensor |

---

Follows [033](033-2026-10-17-printing-the-1st-layer-on-the-a1.md).

## The problem

The user asked how a sensor fits in the pod "given the caster rectangle is in front".

- **The layout was 3 pods:** two at the front, one on each side of the front caster, aimed 20° out; and one at the back, joined to the back caster block.
- **How a sensor goes in:** an HC-SR04P can only enter its pod from behind. The board moves outward along the can axis until the cans pass through the wall, then it's screwed onto 4 bosses.
- **Why the back pod failed:** its board sat directly in front of the back caster block.

**Evidence: a sweep in Fusion.** The test copies the sensor (board, both cans, header), pulls it back along the can axis in steps, and intersects it with the plate at each step.

| Pod | Room behind the seated board | Needed |
|---|---|---|
| front, each side of the caster | > 30 mm, clear | about 12 mm (the cans' length) |
| old back pod | **about 2 mm**, then the caster block | about 12 mm |

So the back sensor could not be fitted. The cans can't tilt in either: there's no room behind the board to swing them.

## The fix: two sensors at each end (the user's call)

The back pod is now the front pair turned 180° about the vertical axis. The front pair is left/right symmetric, so this is an exact mirror front-to-back. The back caster block is the same size as the front one, so the back pods sit beside it just as the front pods sit beside theirs.

| Feature in `1st-layer-v4` | Change |
|---|---|
| 50 `ultrasonic pods (2 front, 2 back, 8 deg up)` | The back pod body was replaced, via `updateBody`, by the rotated front pair. The join (51) keeps its reference. |
| 58 board bosses | Front 8 bosses kept, the back pod's 4 dropped, rotated copies added: 16 bosses, 4 per pod |
| 58 M2 pilots (cut by 60) | Same: 16 pilots |
| 53 old wire slots | Switched off (suppressed) |
| new `ultrasonic wire slots 12x6 x4` | 4 slots at x ±31, z ±88 (model), cut 15 mm down from the deck top as before |

**The half-hole on the back rim** (the user asked about it) was the old back pod's wire slot. It sat at x −58, 124 mm out, so it broke through the edge. It went away with the old slots. The 4 openings still in the rim, at about x ±42, are the radial M3 cover inserts from log 031.

**Checks, all on v11:**
- **Slide-in:** all 4 sensors seat with no overlap, and a 30 mm pull-back is clear for each.
- **Clashes:** the back pods and slots, checked against everything else in the preview (dock in its docked position, drive, covers, boards on the deck), have none. Nothing on the deck covers the new back slots.
- **Mesh:** still a single solid. Only the old Fillet3 warning remains.

## A placeholder error found on the way

The preview's HC-SR04P placeholders sat **7.54 mm too far out**. Their boards ran through the bosses, and the cans stood 8.8 mm proud instead of 1.25.
- **The plate is right:** the bosses end 10.75 mm behind the wall's outer face, as log 032 says. Only the placeholders were wrong.
- **Fixed:** all 4 placeholders are seated now. The preview links `1st-layer-v4` v11 (it was on v9) and is saved.

## Wiring and firmware

- **Pins:** 4 sensors need 8 Teensy pins (TRIG + ECHO each). There's plenty of room; no pins were assigned to the sensors before.
- **Stock:** 2× HC-SR04P (3.3 V) and 2× classic HC-SR04 (5 V). A classic one needs 5 V power and a divider on ECHO (`inventory.md`).
  - **Recommended:** buy 2 more HC-SR04P, so all four wire the same way at 3.3 V.
- **Firing order:** front and back face away from each other. Fire one front sensor together with the opposite back one, in 2 slots of about 60 ms. That gives about 8 readings per second per sensor. Firing all 4 in turn gives about 4.

## Effect on the print (log 033)

| File | Before (3 pods) | Now (4 pods) |
|---|---|---|
| PETG interface | 20 h 28 min, 304 g + 8 g PETG | **22 h 37 min, 324 g + 11 g PETG**, still 168 swaps |
| PLA-only supports | 15 h 44 min, 307 g | **17 h 33 min, 328 g** |

The swap count didn't change. The new pods sit on the same layers as the front ones, so they share the swaps.

## Simulator

- **Re-exported:** the deck and the 16 sensor bodies. The other 110 exports were unchanged, so they were reused. `build_assets.py` then rebuilt the meshes; the URDF came out identical.
- **Physics:** in `physics.py`, the back sensors are now 2 × 9 g at (0, −22, −95), and the deck volume is +11 cm³. The body comes to 4397 g, and the sim's embedded body mass is updated to match.
- **Deployed:** to `gh-pages` (02cd702).

**The dock's sign was invisible to the sim's lidar** (the user spotted this too).
- **Cause:** the ray cast ran `intersectObjects(targets, false)`, which is not recursive. The dock is a mesh inside a scaled group, so every beam passed straight through it, sign and cradle alike.
- **The sign's height was right all along:** its V and ribs span 292–316 mm above the deck top, and the C1's scan plane is at about 304 mm.
- **Fix:** the ray cast now recurses, the dock's meshes are tagged, and beams that end on the dock are drawn green. The readout gives the sign's beam count, distance and bearing.

**`#selftest` now checks the sign:**

| Robot position | Beams on the sign | Nearest | Bearing |
|---|---|---|---|
| on the dock | 69 | 0.17 m | 180° |
| 0.5 m out | 19 | 0.65 m | 180° |
| 1.5 m out | 7 | 1.65 m | 180° |

**Everything else is unchanged** from the deployed baseline, which I ran on the same harness:
- 0 contacts in all 5 poses.
- Hands-up blocks 30°.
- The crossed-arms test pose no longer touches anything. That dates from the 70° mount turn (log 032), not from this change.

## Still open

- **HC-SR04P hole pattern:** still open item 14 (42 × 17 assumed).

## Takeaways

- **Check how each part gets in, not just where it sits.** The pod looked fine with the sensor seated; the problem only shows up along the way in.
- **Check placeholders against the part's own datum.** A placeholder 7.5 mm off can hide or invent clashes.
