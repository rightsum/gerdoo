# 035 — An STS3215 neck, and the lidar raised 45 mm to make room

| | |
|---|---|
| **Date** | 2026-10-17 (open) |
| **Type** | Design decision + work in progress |
| **Status** | ✅ `lidar-holder-v2` · ✅ Dock sign raised 45 mm (`charging-dock-v1` v8) · ✅ `neck-v1`: tilt servo centred under the board section, all sweeps clear · ✅ Preview and simulator updated · ⏳ Print files, Teensy `NECK` commands |
| **Severity** | Medium. The current neck stalls servos and can barely pan before it hits the lidar. |

---

Follows [034](034-2026-10-17-four-ultrasonic-sensors.md).

## What the user asked

- **Servos:** a new neck driven by the 2 spare **STS3215** arm servos, not SG90s.
- **Keep:** the screen and the boards on top as they are.
- **Fix the cables:** better room for the screen's USB, the HDMI ribbon, the lidar cable going down, and the Jetson's 40-pin ribbon.

**The user's choices:**
- Screen: the 5.5" AM-OLED.
- Range: pan ±90°, tilt −15…+30°.
- Brio: stays on the head.
- 40-pin ribbon: spare for now; just leave room for it.
- Height: raise the lidar ~45 mm.

## Why the old neck had to go (from the preview)

- **Tilt:** the screen hangs off the SG90's tilt horn, so the servo holds the head's whole moment all the time. One tilt servo has already died of stalling (`inventory.md`).
- **Pan:** the pan SG90 carries the head's weight directly.
- **Pan clearance:** the Brio (y 254–285) overlaps the C1's height (274–315), and the head's corners come within reach of the lidar post. It can only pan a little before something hits.
- **The screen's driver board** isn't mounted anywhere.
- **Cables:** screen HDMI, touch USB, Brio USB and the servo leads share one Ø17 hole, with no slack loop for panning.

## The STS3215s and the bus

**Stock:** the order was 3 packs × 6 = **18 servos**. The arms use 16, so 2 are spare. `inventory.md` said ×16 and is corrected.

**Wiring:**
- **Same bus as the arms:** Waveshare adapter on Teensy `Serial7`, 1 Mbaud, 12 V.
- **IDs:** neck pan **21**, tilt **22**. Set each with `BUS SETID` with only that servo connected, as for the arms.
- **A third branch:** the adapter's two ports already feed the arms. Add a small bus hub, or a Y-cable made from a spare STS3215 lead with all 3 wires in parallel. The bus is one shared line, and the neck draws well under 1 A.
- **Route:** adapter (1st floor) → T1R power trunk → Ø17 → neck. It needs an extension with the STS3215's own 3-pin connector; the Futaba/JR extensions in stock use a different plug.
- **Firmware:** the Teensy needs `NECK` commands for IDs 21/22, with limits like the arms (EEPROM ranges, multi-turn check). Not written yet, and nothing moves without the user's go-ahead.
- **Retired:** the SG90 gimbal and its 5 V LM2596 servo rail.

## Height: why the lidar moved

An STS3215 with its horn is 49 × 40 × 30 mm, against 23 × 12 × 29 mm for an SG90. The C1 scanned at about 304 mm above the deck top.

**The problem:** a pan servo on the 3rd floor (171 → ~214) plus a tilt stage plus a 110 mm head (screen + Brio) puts the head's top around 330. That's above the scan plane, so the head would blind the lidar to the front.

**Options considered:**

| Option | Cost | Verdict |
|---|---|---|
| **Raise the C1 45 mm** | Reprint the small holder; move the dock sign up 45 | **chosen** |
| Sink the pan servo through the 3rd floor | Reprint the 250 mm 3rd floor, and still tight when tilted | no |
| Take the Brio off the head | Loses look-where-you-look; still tight | no |

## `lidar-holder-v2`

A copy of the user's `lidar` file (left untouched), in Default Project.

**Post:**
- Ø16 × 100 → **Ø24 × 145**. The post is 45 mm longer but about 2.3× stiffer in bending, so tip deflection is about 1.3× the old one, against the C1's 10 Hz spin.
- Printed volume 29 → 69 cm³.

**Cable groove:** 6 × 6 mm, down the whole post on the **robot's back side**, starting under the plate.
- The C1's lead (XH2.54-5P at both ends, about 15 × 6 mm) presses in. No connector has to fit through the post.
- At the foot it drops straight into the existing 14 × 9 lidar slot, about 20 mm behind.
- **First version** cut the groove through the plate too. The user pointed out that the C1's cable leaves from its **side**, so that slot was closed.

**C1 either way round:**
- The C1's 4 holes are 0.8 mm off centre (20.7 / 22.3). A second hole at each corner now takes the C1 turned 180°.
- **Why:** if the socket faces the front, its cable would hang right where the head swings past the post, with about 5 mm of clearance at full pan. Turning the C1 puts the cable at the back.
- **If it's turned,** set a 180° yaw offset on the lidar in the driver or URDF.

**Unchanged:**
- The C1 plate.
- The Ø4.4 insert at the foot, so it bolts to the same centre hole in the 3rd floor.

**Result:** the plate is now at 316–319 above the deck top, the C1 at 319–360, and the scan plane at about 349.

## Dock sign raised 45 mm (`charging-dock-v1` v8)

The sign's V and ribs have to stay in the C1's scan band. They move from y 292–316 to **337–361**.

**How:** at the end of the history:
1. Split the mast at y 150.
2. Move the top piece (with the half-lap tongue), the sign head, the 6 letters and the diffuser up 45 mm.
3. Fill the gap by extruding the mast's own cross-section. The back LED wire groove carries through.
4. Rejoin the mast as one solid.

**Print fit:** the mast is now 227 mm tall and the head 153 mm, both inside the A1's 256. No errors in the history.

## The neck: `neck-v1`

**What's fixed:**
- **The user's parts:** `screen` and `screen-board` are used exactly as designed.
  - The board bracket sits flat on the screen block, with its 45° plate going back and **down**, as the user specified.
  - The only change is the 4 M3 screws, 4 mm longer (about M3 × 16).
- **The 3rd floor:** untouched. The pan base uses the old neck's 4 M3 inserts.

**Layout, above the deck top, in the preview frame:**

| Item | Where |
|---|---|
| Pan axis | z 95 |
| Pan servo | standing, shaft up, **lifted 8.5 mm**: case bottom at y 183.25, horn top at y 217.7 |
| Tilt axis | along x at y 236, z 94.5: 20 mm behind the screen face, 26 mm below the screen's centre (screen centre y 262) |
| Tilt servo | lying flat, **centred under the board bracket**, body pointing back. Horn on +x, idler horn on −x (faces at x ±18.5). |
| Head | screen y 224–300, Brio on the screen's own ledge, the whole head under the board bracket's shelf |

**New printed parts:**

| Part | Volume | Fixing |
|---|---|---|
| Pan base | 17.5 cm³ | 4 × countersunk M3 into the old neck inserts. The servo rests on two side ledges, 8.5 mm above the floor. The floor is open under its cable sockets, with a channel to the Ø17 hole. Walls notched for screwdriver access. |
| Pan clamp | 0.7 cm³ | Strip over the pan servo's cable end. 2 × M2 into its top rails, 2 × M3 into Ø4.4 inserts in the base walls. |
| Arm | 6.3 cm³ | Hub + plate on the pan horn (4 horn screws, flush under the tilt servo). The plate carries the tilt servo directly, with cheeks at its back end and 2 × M2 on each side. The socket-side cheek is short so the tilt servo's plugs fit. Open at the back for the cables. |
| Head yoke | 11.6 cm³ | Pad on the back of the board bracket's base, held by the same 4 M3 into the screen block. Two arms down to the horn and the idler horn: 4 + 4 countersunk screws from outside. Pad's back-bottom edge chamfered 2 mm. |

**Wrong turns:**
1. **First version: tilt servo beside the board bracket, horn only.** It worked, but the user found it "very beefy on one side". Centring it under the board section was their idea.
   - The servo can't sit further back under the board plate. Looking up, the plate's underside, where the driver board sits, swings into it.
   - So it sits under the screen block instead.
2. **The tilt plate was first clamped *between* the block and the board bracket.** That pushed the bracket 3 mm back, and the user noticed. It now clamps behind the bracket's base.
3. **Measured, not guessed:**
   - The screen block's back face is at 18.3 mm, not 18.
   - The STS3215's mounting holes sit on side rails, at +0.95 and −31.05 along the shaft, with a raised centre strip at +2.05 and a cable bump on the back face. The first cheeks cut into all of them.
   - The horn's 4 holes form a 14 mm square on the servo's own axes. A rough frame had put them 16° off.

**Checks, in Fusion, with booleans on the posed bodies.** Assumed driver board: a 45 × 45 × 10 mm envelope on the plate's underside.

| Check | Result |
|---|---|
| At rest | No overlaps (the horns inside their own servo are excluded) |
| Tilt, 15° face-down to 30° face-up | Head, yoke and driver board clear of the tilt servo, arm, pan servo, base and clamp. One 0.3 mm graze at 30° up, fixed by the chamfer. |
| Pan ±90° in 10° steps, at tilts +15, 0, −15, −30 | Clear of the lidar post, C1, pan base, clamp and pan servo |
| Head's highest point | 331.6 mm, 17 mm under the scan plane |
| Lowest moving part | Arm hub at 209 mm |

## The cable sockets (found by the user while fitting)

**The problem:** the STS3215's two sockets are on its underside, at the cable end, and the plugs go in pointing down. The pan servo stood on the base floor, so there was no way to plug a cable in or out. The tilt servo lies on its side, so its sockets face the idler side and its cradle cheek.

**Fix:**
- **Pan servo lifted 8.5 mm.** That's the most possible without moving the head: the arm's plate now sits right under the tilt servo instead of on a riser. The head and the scan-plane margin are unchanged.
- **The base floor is open under the sockets.** There's 10.3 mm down to the 3rd floor top, and a channel runs back to the Ø17 hole.
- **To fit or remove the pan servo:** plug the cable in, lower the servo onto its ledges with the wires bending back into the channel, then fit the clamp. To unplug, take the clamp off and lift the servo.
- **The tilt servo's socket-side cheek is shortened** to the screw holes only.

**Re-checked:** no overlaps at rest; tilt clear at +15, +7.5, 0, −15, −30; pan ±90° clear at tilts +15, 0, −15, −30.

**Still to confirm:** the plugged-in height of the plug plus the wire bend. If it's over 10 mm, the whole neck can rise a few mm. The scan-plane margin is 17 mm.

## Wiring the neck to the bus

**A third branch:** the Waveshare adapter's two ports are the same bus, and both feed an arm. Add the neck by either:
- a small bus servo hub on one port, or
- a Y-cable made from a spare STS3215 lead, with all 3 wires joined straight through.

**Chain:** hub → pan servo (21) → its second port → tilt servo (22).

**Route:** T1R → Ø17. It needs an extension about 40 cm long with the STS3215's own 3-pin plug.

**Set the IDs with the arms unplugged.** New servos ship as ID 1, the same as the left arm's J1 (log 028).
1. Plug in one neck servo alone and run `BUS SETID 1 21`.
2. Swap to the other and run `BUS SETID 1 22`.
3. Reconnect the arms.

**Before any neck motion:** the Teensy needs `NECK` commands with limits (pan ±90°, tilt −15…+30°).

## Simulator (deployed, `gh-pages` c518b92)

**Meshes:**
- **Fixed** (`neck_static`): pan base, clamp, pan servo.
- **Pans** (`neck_pan`): arm, pan horn, tilt servo.
- **Tilts** (`neck_tilt`): screen, board bracket, Brio, yoke, horns.

**Joints:**
- Pan on the real axis (95, 0, 209.2 + ground), ±90°.
- Tilt on (94.5, 0, 236 + ground), −15…+30°.
- Lidar at 319.

**Page:** the face texture moved onto the new screen. The dock light moved up 45 mm.

**`physics.py`:** new parts and positions. The body is now 4547 g with its centre of gravity at 131 mm, and the total at rest 5641 g. The sim's braking limit at rest goes 0.39 → 0.37 g.

**`#selftest`:**
- 0 contacts in all 5 poses.
- Lidar 360° clear at rest.
- Dock sign detected (69 / 19 / 7 beams).
- **Hands-up now blocks 45° of the scan** (was 30°). The higher scan plane crosses more of the raised arms.

## Idle pose (the user's)

Posed in the simulator and made the startup pose there. Arms folded down beside the body, mirrored onto the right arm:

| Joint | J1 | J2 | J3 | J4 | J5 | J6 | J7 | Gripper |
|---|---|---|---|---|---|---|---|---|
| Value | −73° | 52° | 33° | −9° | 135° | 101° | 81° | 74 % |

- **Simulator:** no contacts, lidar 360° clear. The centre of gravity is 137 mm up, against 160 in Rest, so the braking limit is 0.42 g instead of 0.37.
- **Deployed:** `gh-pages` 0d53f34.
- **Real robot:** this would be the natural pose to park the arms in once the panel or firmware has a "go idle" command. That isn't done.

## Colour

**The robot will be printed all black** (the user's decision).

The simulator now shows every printed part in matte black PLA, with the servos a shade darker:
- deck, floors, covers;
- arm bases and the ElRobot arms' printed links;
- lidar holder and neck.

**Unchanged** (bought parts, or not part of the robot):
- copper posts;
- drive motors;
- boards;
- casters;
- dock.

Deployed as `gh-pages` 6e3a6bd.

## Still to do

- **Print files** for the 4 neck parts and `lidar-holder-v2`.
- **Teensy `NECK` commands** with limits.
- **A slot for the 40-pin ribbon:** it doesn't fit the Ø17 hole. It depends on whether the 3rd floor is already printed.
- **Measure the driver board** (size, thickness) and check it against the 45 × 45 × 10 envelope.

## Print file: the neck parts and the lidar holder on one plate (2026-10-24)

**Orientations:** each part was scored in all 6 axis orientations for bed contact and down-facing area flatter than 45°, then the best one got the voxel floating check.

| Part | Printed | Overhang left |
|---|---|---|
| lidar holder v2 | plate down, post up (its own file's orientation) | none |
| pan base | floor down, as fitted | two ~8 mm bridges over the wire notches |
| head yoke | upside down | only screw-hole tops (≤ 7 mm²) |
| arm | lying on its side (+z up) | only hole tops (≤ 3 mm²) |
| pan clamp | flipped | none |

**Settings:** no supports, no PETG. 0.16 HQ, **5 walls, 40 % infill** (the neck carries the head), 4 mm brim, travel acceleration 3000, z-hop 0.8 spiral.

**File:** `~/Downloads/gerdoo_neck_lidar_A1.3mf` (spec `sim/web/tools/plate_neck_lidar.json`): **6 h 54 min, 96.8 g**, no warnings.

**Hardware, from the parts above:**
- **Pan base:** 4 × countersunk M3 into the old neck inserts in the 3rd floor.
- **Clamp:** 2 × M2 into the pan servo's top rails, and 2 × M3 into Ø4.4 inserts in the base walls.
- **Arm:** the 4 horn screws, plus 2 × M2 on each side of the tilt servo.
- **Yoke:** the 4 M3 of the board bracket, about M3 × 16, 4 mm longer than before. Plus 4 + 4 countersunk screws into the horn and the idler horn.

**Still open:**
- the plug-plus-bend height under the pan servo (≤ 10 mm assumed);
- the screen driver board's real size (a 45 × 45 × 10 envelope is assumed);
- the Teensy `NECK` commands, before anything moves.

**The head yoke fell twice, at about 80 % of its height (2026-10-25):**
- **The user's photo:** the yoke after the fall, with damage on top of an arm.
- **Cause:**
  - Printed upside down, the yoke's two arms (3.5 mm thick, 24 mm deep) stand **29 mm free** above the pad (print Z 22–51).
  - The horn holes (Ø7, Z 42) and the screw holes and countersinks (Z 35/42/49) sit near their tops.
  - The nozzle pushes along the arms' thin direction (print X). So the arms flex, a curled hole edge catches, and the part goes over.
- **I first blamed the front cover by mistake** and added ±40° braces to it (log 042, front cover plate v7). Those braces are harmless, but not what was asked.
- **Fix:** `stabilizer_fins.py yoke` adds **4 snap-off fins** outside the arms, two per arm, from the bed to Z 45, 18 mm wide on the bed.
  - They sit in the z bands 83–86 and 103–106, either side of the horn screw holes.
  - The 20 tabs (1.5 mm, every 8 mm) stop at Z 36, below the countersinks.
  - Fusion check: 0/140 fin samples inside the yoke, all 20 tabs anchored.
- **Plate:** `~/Downloads/gerdoo_neck_lidar_v2_A1.3mf`, **7 h 28 min, 102.5 g**, no warnings. v1 removed.
- **Better (the user asked whether the shape itself was the problem): the yoke now prints on its back.**
  - **Why upside down was wrong:** printed upside down, the arms stand tall and thin, and their layers stack along the arm length. That's their weak direction in use, since the arms carry the whole head through the tilt horns.
  - **On its back** (+z up, map `x,y,z`, 24 mm tall):
    - the arms lie on their 24 mm edge and print in their strong direction;
    - nothing stands free;
    - the horn holes print as horizontal holes (Ø7 tops bridge fine).
  - **Cost:** the pad sits about 6.5 mm above the bed. A manual **grid support** under it (one enforcer box) with the **2-layer PETG interface** takes care of it, with a 35 mm prime tower.
- **Plate:** `~/Downloads/gerdoo_neck_lidar_v3_A1.3mf`, **7 h 4 min, 100.2 g PLA + 0.6 g PETG, 2 swaps**, no warnings. v2 (fins) removed. The `yoke` mode stays in `stabilizer_fins.py` but isn't used.
