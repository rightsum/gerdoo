# 029 — Arm mounts on the first layer: measurements, a merged round base, and the load numbers

| | |
|---|---|
| **Date** | 2026-10-16 (open) |
| **Type** | Design decision — where and how the two ElRobot arms sit on the robot |
| **Status** | ✅ `1st-layer-v4` started, with standoffs for the Teensy breakout · ✅ Arm base concept checked for load and clearance · 🔄 J1 can only turn ±89° with ElRobot's J1 bracket; a full turn needs a new layout · 🔄 Tyre-top height, 2nd floor, breakout holes and arm mass still to measure |
| **Severity** | Low — design work, nothing printed yet |

---

## Context

The base plate (`down-panel-v3` in Fusion) predates the arms, the two battery
packs and the Teensy. All new work goes into a copy, **`1st-layer-v4`**, so v3
stays untouched.

The plate is modelled **upside down** in Fusion. The robot's top deck is the
y = 0 face, and the casters and motor pockets sit on +Y. Fusion's *bottom*
view is the robot seen from above.

| Hole group (deck view) | What it is |
|---|---|
| M4 at 73 × 81.7, upper centre | the two-layer BMS stack |
| two M3 squares at 39.6, lower left and right | the two BTS7960 (IBT-2) drivers |
| M3 at 19 × 55, between the drivers | the old Nano-era board. **Suppressed in v4** (`Hole10`, `R-Pattern6`) |
| M4 at 25 × 29.6 in each motor pocket | the 36GP-555 L-brackets |

## The Teensy breakout

The Teensy goes on a Treedix screw-terminal breakout (inventory, *Co-processor*),
between the two drivers. The board's long axis runs front to back, so each
terminal row faces one driver. The USB end faces the centre cutout.

- **4 standoffs:** Ø6.5 × 6 mm, with Ø3.2 holes for M2 heat-set inserts,
  7 mm deep (6 mm of standoff plus 1 mm into the deck).
- **Positions:** x ±18.55, z −36.6 / −99.4.
- **Parameters** start with `tb_`. ⚠️ The hole spacing (62.8 × 37.1 mm) was
  scaled from the vendor drawing, not measured.
- **Recommended:** Ø7 standoffs. At Ø6.5 the wall around a hot insert is only
  1.65 mm.

## Measured on the robot

| What | Value | How |
|---|---|---|
| Wheel diameter | **66.3 mm** | calipers |
| Wheel width | **26.3 mm** | calipers |
| Plate flat to wheel outer face | **41.4 mm** | calipers |
| ⇒ wheel inner face | flat + 15.1 mm | 41.4 − 26.3 |
| ⇒ wheel centre from plate centre | **145.7 mm** | 117.4 + 41.4 − 26.3 / 2 |

The flat sits 117.43 mm from the centre: a Ø250 disc with an 85 mm chord cut
off each side.

## Taken from datasheets and ElRobot's model

**36GP-555 motor** ([rcdrone](https://rcdrone.top/products/36gp-555-planetary-dc-gear-motor-with-encoder),
[Precision Microdrives](https://precisionminidrives.com/product/36mm-dc-planetary-gear-motor-with-encoder-model-nfp-36gp-555-en)):

- **Body:** Ø36 mm.
- **Length:** gearbox 34.5 mm for 27:1 (≈ 170 rpm at 12 V, which fits the
  160 rpm we bought), motor 57 mm, encoder 12 mm. About 104 mm in all.
- **Shaft:** Ø8 mm D-cut, sticking out 20 mm.
- **Front face:** 4× M3 on a 28 mm circle, with a Ø22 mm locating boss.
- **Placed in the preview:** each motor runs from the bracket flange at the
  flat (x = 114.4) inward to x = 10.9. The two encoders end 22 mm apart in
  the middle.

**ElRobot follower** ([norma-core](https://github.com/norma-core/norma-core/tree/main/hardware/elrobot),
`STEP/ElRobot.stp` and `simulation/elrobot_follower.urdf`):

- **J1 axis** in the STEP frame: x = 36.75, y = 34.55 mm. Found from the
  4 horn screws.
- **J1 limit:** ±1.5509 rad = **±88.9°** (URDF).
- **J1 bracket:** a U-shaped bracket that wraps around the J1 servo. It holds
  the top horn *and* the bottom idler horn, and its lowest point is 9.6 mm
  above the base bottom.
- **Radius around J1 swept by the turning parts:**

  | Height above base bottom | Radius |
  |---|---|
  | below ~73 mm | 33 mm (J1 bracket and J2 servo) |
  | above ~73 mm | 108 mm (shoulder) |
  | above ~100 mm | 240 mm (whole arm) |

## Assumed — not measured yet

| What | Value used | Where it comes from | Matters for |
|---|---|---|---|
| Axle height | 33.5 mm below deck top | caster block 20.2 mm + 1" caster 37.8 mm ⇒ floor about 66 mm below the deck top; minus the wheel radius | the gap between tyre and base |
| ⇒ tyre top | 0.35 mm **below** the deck top | follows from the row above | everything above the wheel |
| Arm mass | 1.0 kg | 8 × STS3215 at ≈ 55 g, plus prints and camera | loads, tipping |
| Payload | 0.3 kg at full reach | guess | loads |
| Rest of the robot | 4 kg, centred | guess | tipping |

**Measure next:**
- the deck-top height and the tyre-top height, robot standing on the table
- one arm on the scale
- the 2nd floor's height above this layer, and its outline

## The arm base, as it stands

The design moved through three shapes. Each one is in **Wrong turns** below.

**The arms face the front** (+z in the preview), the Teensy and driver side.
The batteries are at the back.

The current concept is one printed part per side:
- **Foot:** an ellipse on the deck, 40 × 52 mm, over the 4 motor-bracket bolts.
  It started at 56 mm; see the driver clash below.
  The bolts are M4 and come up from **underneath**: through the steel bracket
  base, through the plate, into M4 heat-set inserts in the foot.
- **Neck:** a lofted shape that leans out over the wheel, R6 blend at the top.
- **Disc:** Ø90 × 8 mm, underside **30 mm above the tyre** (y = 29.6). Its
  centre sits 12 mm behind J1, so the housing fits on it with J1 directly over
  the wheel centre. It started at Ø80 with the centre 22 mm back. That made
  the neck widen toward the drivers and clip each IBT-2 board's corner.
- **Driver keep-out:** a 2 mm clearance box around each IBT-2 is cut out of
  the neck.
- **On top:** only ElRobot's **J1 servo housing**, joined straight onto the
  disc. In the STEP frame it runs x 43.9–82.8, y 13.5–55.5. The table-mount
  ears, their countersunk holes and the rest of the foot are gone; they were
  for clamping the arm to a table.
- **No foot needed under J1:** the disc top is flat. The J1 bracket's lowest
  point clears it by 9.6 mm, the bottom-horn screws by 7.2 mm, and the J1
  servo's underside by 8.2 mm.

**Parameters** (`ab_*`): `ab_lift` 29.6, `ab_disc_t` 8, `ab_disc_d` 80,
`ab_foot_t` 9, `ab_sweep_r` 35.

**Clearances**, measured in Fusion with the preview parts:

| Between | Gap |
|---|---|
| base neck ↔ tyre | **6.4 mm** (lowest point of the neck, at the plate edge) |
| disc ↔ tyre | 30 mm |
| base ↔ motor bracket | 7 mm (the plate sits between them) |
| base ↔ moving arm parts, and ↔ the arm turned to J1 ±89° | no overlap |

| base ↔ IBT-2 heatsink / board | 4.1 mm / 12 mm |
| IBT-2, Teensy, BMS stack, posts ↔ arms and their ±89° positions | no overlap |

**Other overlaps:**
- **Stock ElRobot parts:** the servo in its pocket and screws into the base,
  as they come in the STEP.
- **A 0.1 mm graze at J1 = ±88.9°:** the J1 bracket meets its own housing.
  That's ElRobot's mechanical stop, and it is where the URDF's limit comes
  from. Keep the firmware's J1 range a few degrees inside it.

**Electronics stand-ins** in the preview:

| Part | Size | Where the size comes from |
|---|---|---|
| IBT-2 drivers | 50.2 × 49.1 × 40.9 mm, heatsink under the board, on 22 mm M3 standoffs | **measured** |
| Power/motor terminals | facing out | |
| 8-pin control header | facing the Teensy | |
| Treedix breakout | per its drawing, with the Teensy on headers | drawing |
| BMS stack | two 70 × 77 × 23 mm holders on 62 mm posts | **guessed** |
| Six 2nd-floor posts | 70 mm tall | **guessed** |

## Load calculations

### Design moment at the arm base

Arm straight out sideways, payload at the gripper:

```
M_static = g · (m_arm · r_com + m_load · r_load)
         = 9.81 · (1.0 kg · 0.15 m + 0.3 kg · 0.33 m)
         = 2.44 N·m
```

- **Cap:** the shoulder servo (J2) stalls at 30 kg·cm = **2.94 N·m**, so the
  arm cannot push harder than about 3 N·m on its own.
- **Offset load:** J1 sits 48 mm outboard of the foot centre (145.7 vs
  97.4 mm). That adds 12.8 N · 0.048 m ≈ **0.6 N·m**.
- **Design value:** ≈ 2.7 × the static moment, for bumps and fast moves:
  **M = 8 N·m**.

### Neck at the deck (the weakest section)

The section is an ellipse with semi-axes a = 20 mm (x, sideways) and
b = 26 mm (z).

```
S_z = π·a²·b / 4 = π·20²·26 / 4 = 8 168 mm³   →  σ = 8 000 / 8 168  = 0.98 MPa
S_x = π·b²·a / 4 = π·26²·20 / 4 = 10 619 mm³  →  σ = 8 000 / 10 619 = 0.75 MPa
```

- **Strength:** PLA and PETG hold about 10–20 MPa across layers (the weak
  direction), so the margin is **over 10×**.
- **With partial infill:** if walls and infill carry only 40 % of the solid
  section, the margin is still over 5×.

### The 4 M4 bolts into heat-set inserts

The bolts sit on a 25 × 29.6 mm pattern:
- along x at 84.9 / 109.9
- along z at ±14.8

The foot is an ellipse: x 77.4–117.4, z ±26.

**Method:** the foot tips over one edge, so each bolt's tension grows with
its distance d from that edge:

```
F_i = M · d_i / Σ d²
```

A first pass divided M by the 25 mm row spacing instead. That gave
160 N per insert: too high for 4 bolts, and blind to which two bolts matter.

| Bolts | Tip outward (edge x = 117.4) | Tip inward (x = 77.4) | Tip forward / back (z = ±26) | Worst |
|---|---|---|---|---|
| **all 4** | 117 N | 117 N | 91 N | **117 N** |
| 2 inner only | 123 N | **533 N** | 182 N | 533 N |
| 2 outer only | **533 N** | 123 N | 182 N | 533 N |
| 2 diagonal | 234 N | 234 N | 182 N | 234 N |

- **Pull-out:** M4 brass inserts in PLA or PETG are commonly quoted around
  600 N or more.
- **All 4 bolts:** about **5×** margin.
- **One row of 2:** about 1.1×, which is not enough. That row sits only
  7.5 mm from one of the tipping edges, so it holds that direction with
  almost no leverage. Inner-only bolts fail when the arm reaches across the
  robot, and outer-only bolts fail when it reaches out over the wheel.
- **2 diagonal bolts:** about 2.5×. That's acceptable but thin.
- **J1's twisting load** (2.94 N·m stall) shows up as sideways force on the
  4 bolts, 19.4 mm from the pattern centre: about 38 N each. Clamping
  friction carries it.
- **Backing:** the steel bracket base sits under the 7 mm plate in the pocket,
  so the plate is clamped between steel and the foot.

### Tipping the robot over

Moments are taken about the tipping line:

```
sideways, one arm straight out over its wheel:
  over  = 1.3 kg · 0.15 m  = 0.195 kg·m
  hold  = 4 kg   · 0.146 m = 0.58 kg·m    → ≈ 3×

forward, both arms past the front caster (caster at 90 mm, arm load centre ~150 mm):
  over  = 2 · 1.3 kg · 0.06 m = 0.156 kg·m
  hold  = 4 kg · 0.09 m       = 0.36 kg·m  → ≈ 2.3×
```

Both are stable standing still. Don't drive fast with the arms reaching out.
The 4 kg is a guess; redo this once the robot has been weighed.

### Printing

- **Material:** PETG or PLA+.
- **Walls and infill:** 5 walls, 40–50 % gyroid infill.
- **Inserts:** M4 brass in the foot, from below.
- **Orientation:** disc on the bed. The neck then narrows going up, so it
  needs no supports.

## The whole robot in the preview

**Orientation rule:** each of your plate models is drawn in its own
orientation, so check each one against the robot before placing it.
- The **1st layer** is drawn upside down: turn it over about the side-to-side
  axis.
- The **2nd and 3rd floors** are drawn the right way up but **front-to-back
  reversed**: turn them 180° about the vertical.
- The **C1 holder** is drawn post-up. On the robot the post goes down into the
  3rd floor's centre hole, and the square plate holding the C1 is on top.

Heights are above the 1st-layer deck top. Front is +z, toward the Teensy and
drivers; the batteries are at the back.

| Level | What | Height |
|---|---|---|
| under the 1st layer | 3 HC-SR04P pods, below | |
| | └ 2 front | aimed ±20° out, one each side of the front caster |
| | └ 1 back | joined to the back caster block |
| | └ all 3 | tilted 8° up; pocket open at the back, notch for the pins |
| 1st layer | IBT-2 ×2 (measured), Treedix + Teensy, 3S2P stack 103×88×45 (listing) | deck at 0 |
| 1st → 2nd posts | `separator` hex, 77 mm, on the 125×180 corners; Ø16 round posts at (±47.7, 0) into the 2nd floor's Ø17 recesses | |
| 2nd floor | underside 77, top 87 | |
| | └ UPS (C) | in the 102×78.7×3 pocket |
| | └ Jetson Orin Nano dev kit | above the UPS, top at 150 |
| | └ antenna brackets | at the back corners |
| | └ arm notches | R 76 |
| | └ speaker mount | removed |
| 2nd → 3rd posts | `separator-2nd-short` hex, 74 mm, on the same 125×180 corners | |
| 3rd floor | underside 161, top 171 | |
| | └ arm notches | R 100 |
| | └ neck holes | moved 18 mm back with the face |
| neck + face | SG90 pan/tilt (approx) | |
| | └ screen | `screen` model, 178–254, front at z 104, so its corners line up with the edge |
| | └ Brio | on top, at 254–285 |
| top | C1 holder (your model), C1 at 274–315 | scan window ≈ 300, clears the Brio by ~14 mm |

**Two antenna points:**
- They belong on the 2nd floor; their brackets were made for it. The whips
  run up beside the 3rd floor and top out around 205 mm, well below the
  lidar's scan plane.
- The lidar is not an RF noise source. The real risks are a whip in its laser
  plane, and USB3 near the WiFi card.

**The arms against the floors.** In ElRobot's resting pose the upper arm folds
back behind J1. Turning J1 outward swings that elbow inward over the floors.
Floor material reached by the arm, as distance from J1 (J1 swept −30°…+89° in
5° steps):

| Floor | J1 0° | ±15° | 0…+89° | −30° |
|---|---|---|---|---|
| 2nd | 0 | 32–55 | 66 | 32 |
| 3rd | 54 | ~100 | 122 | 158 |

- **2nd floor:** a notch of 76 mm (66 + 10 buffer) clears the arm at every
  angle.
- **3rd floor:** it sits at elbow height. A 100 mm notch is the most it can
  give before losing the lidar post and the corner posts. With the elbow
  folded back, that leaves J1 about ±10° at that height.
- **The fix is a choice to make:** raise the 3rd floor above the folded elbow
  (~260 mm), narrow it to a spine, or keep the elbow out of that zone in
  firmware.

### After the crash: what is saved where

- **`1st-layer-v4`, version 2:** the 18:42 crash backup was out of date, so
  the steps were replayed by script onto the saved v1. It now has:
  - the Teensy standoffs
  - the old Nano and 25×30 hole groups switched off
  - the 3 sensor pods
- **`gerdoo-assembly-preview`** (new file in Default Project, saved after each
  step) holds the whole-robot preview:
  - **Plate:** a **linked** copy of `1st-layer-v4`, so edits there show up.
  - **The rest:** static copies of the floors, holder and screen, plus the
    arms from ElRobot's STEP and stand-ins for everything else.
  - **Not rebuilt yet:** the see-through J1 sweep copies.
- **The crash backup** is kept in the session scratchpad as
  `1st-layer-v4_recovered_1842.f3d`.

### Open points

- **Post holes 5 mm off.** Your 1st layer and 2nd floor both have their
  corner post holes at x = −60 and +65. Turning the 2nd floor front-to-back
  mirrors them to +60 and −65, which misses the posts by 5 mm. Either the
  real 2nd floor's corner holes move, or one of the plates faces the other
  way.
- **The 3rd floor is very narrow.** With an R100 notch per side it is only
  ±46 mm wide at the arms' line. Decide: raise it above the folded elbow
  (~260 mm), narrow it to a spine, or limit the elbow in firmware.
- **Still to do:** the neck modelled from the listing photos, and rounding
  the notch corners.

## Fit plan for the remaining electronics (preview: `Fit study` and `Covers`)

**Sizes and where they came from:**

| Part | Size | Source |
|---|---|---|
| reSpeaker XVF3800 core board | 70.5×52.2 mm PCB, ~12 mm tall, 4× M3 on 62.5×44.2 | Seeed STEP |
| reSpeaker circular mic array | a **ring**: OD 72.5, ID 52.5, 1.51 mm PCB (2.9 with the mics), 3× M3 at r 31.25 (120°). Corrected in log 030 | Seeed STEP |
| └ its 4 sound ports | Ø1 at (±22, ±22), on the **back** of the board | Seeed STEP |
| └ cable to the core board | 20 cm | Seeed |
| Bus Servo Adapter (A) | 42×33, M2.5 holes on 37×28 | Waveshare |
| 1.69" LCD | 31.5×39 mm | Waveshare |
| MINI560 | 29×18 | inventory |
| LM2596S with voltmeter | 66×35 | assumed |
| XL4015 CC/CV with heatsink | 52×27×18 | assumed |
| D4184 | 33×18 | assumed |
| Yahboom USB hub | 75×55 | assumed (still in delivery) |
| Speaker | 40×40×18 | assumed (not in the inventory) |

**Base layer.** The deck is full, so the six boards **stand on edge** in four
printed holders. Each holder fills one of the 21 mm free strips between the
middle posts, the centre cutout, the arm feet, the BMS and the drivers:

| Strip | Boards |
|---|---|
| left outer | LM2596 (neck servos 5 V) |
| left inner | MINI560 + D4184 (light strip) |
| right outer | XL4015 charger, heatsink vertical |
| right inner | servo adapter + voltage sensor |

No overlaps. Nothing hangs under the plate (the user turned that down).

**2nd floor:**
- **XVF3800 core board** at the front, behind the chest. The mic array's
  cable is only 20 cm.
- **USB hub** at the back, on 8 mm standoffs. The rear pair sits in the gap
  between the antenna tabs.

**Speaker:**
- **Where:** under the 3rd floor at the **back centre**, screwed up from
  below.
- **Grille:** cut a grille above it and add a mesh cap on top.
- **Why not the old spot:** the original spot (the 38×38 M3 blind holes,
  front-left) now sits under the standard corner post.

**Front cover ("Iron Man" chest), concept:**
- **Shell:** 2.5 mm, ±45° of the front arc, from the plate underside to the
  3rd floor top. It is screwed to the deck by 3 tabs at 0° and ±25°.
- **Heart:**
  - a boss with the mic array mounted behind it, back side out
  - 4 acoustic holes on the ports
  - 3 M3 points for the array
  - a front pocket for the 1.69" display, with a slot behind it for the
    display's wires
- **Smile:** a raised channel for the COB strip, with a wire hole at one end.
- **Light sensor:** a window, top right.

**Back cover, concept:**
- **Shell:** ±45°, from the plate underside to below the 2nd floor, so it
  stays clear of the antenna brackets.
- **Holes:** the DC-022B jack (Ø8) and the light potentiometer (Ø7).
- **Dock:** a boss holding two Ø5.5 pogo pins, 24 mm apart, at the bottom
  centre.
- **Mounting:** 3 tabs into the deck at 180° and ±44°. They clear the BMS
  and the copper posts.

**Wiring, and the holes it needs:**
- **2nd floor:**
  - A **front centre slot** for the light strip, light sensor, neck servo
    5 V and display.
  - A **back centre slot**, between the antenna tabs, for 12 V to the UPS,
    the hub and the XVF3800, plus the Teensy's USB.
  - Arm cables run past the notches.
- **3rd floor:**
  - The existing Ø17 hole at the front takes the screen, Brio and neck
    cables.
  - A new Ø12 hole beside the lidar post takes the C1's USB.
  - The speaker wires stay between floors 2 and 3.
- **Display:** driven by the XIAO on the XVF3800 board, which is a short run.
- **Charging path:** dock pins and DC jack → XL4015 → Schottky → packs.

**Superseded by [log 030](030-2026-10-16-front-and-back-covers-and-the-cable-plan.md)**, which
built the covers, the cable trunks and the speaker grille. It changed the ports
and the tab angles above and named the trunks. What this list said was not
built yet:
- the covers as their own printable parts
- the holder and cover-tab insert holes in v4
- the cable slots in the 2nd and 3rd floors
- the speaker grille, which waits on `3rd-floor-v2` being saved and on the
  speaker's real size

## Wrong turns

- **Fusion Part documents hold one component.** `1st-layer-v4` is a Part, so
  the arm preview lives in a separate Assembly (hybrid) document. The plate in
  there is a **static copy** of v4, and it won't follow edits to v4.
- **A part moved by a script snaps back** unless a position snapshot is taken
  (`design.snapshots.add()`). The first arm placement was silently undone.
- **A script that throws is rolled back as a whole** over the Fusion MCP. Two
  edits vanished because a later line raised. Keep checks that can fail in
  their own call.
- **Stick braces.** The first pedestal was a foot, a wall, a disc and two
  diagonal braces. It worked but looked bad, and was replaced by one lofted,
  filleted part.
- **A separate pedestal under ElRobot's base.** Its trimmed core lost the
  foot's recesses for the J1 horn screws: they hung 0.8 mm into the disc.
  The fix was to keep ElRobot's foot inside the disc circle.
- **The floors were first flipped upside down,** when "vice versa" meant
  front-to-back. The 2nd floor's pocket and Ø17 recesses only make sense
  turned front-to-back: UPS pocket up, recesses down onto the 1st layer's
  middle posts.
- **The screen first sat on top of the neck,** about 50 mm too high, and
  hid the lidar. Then it sat at the front edge, and its corners stuck out past
  the round edge. The photos showed it hanging low on the tilt horn, inside
  the body.
- **Fusion crashed** during a clash check across every body in the preview
  (~200 bodies against ~300). Check clashes in smaller batches.
- **A round shell around the housing** looked like one round tower, but it
  boxed J1 in. The user wants **J1 to turn a full circle**. That was removed.
  More to the point, ElRobot's U-shaped J1 bracket hits its own servo past
  about ±90°, so no shell or base shape can give a full turn on its own.

## Next

1. **J1 full rotation:** stand the J1 servo upright below the disc, and make a
   new turntable part for J1 that sits on the top horn plus a thrust bearing,
   carrying the J2 servo where ElRobot puts it. Then nothing turning sits
   below the turntable. Without a slip ring, the servo cable limits how far
   J1 can wind before it has to turn back.
2. Measure the tyre-top height, then set `ab_lift`.
3. Get the 2nd-floor height and outline. A full Ø250 floor above would block
   the shoulder.
4. Measure the breakout holes and the M2 insert diameter, then set the `tb_*`
   parameters.
5. Save `1st-layer-v4`, then swap the static plate copy in the preview for a
   linked one.

## Takeaways

- **Take dimensions from the vendor's CAD, not from the photos.** ElRobot's
  STEP and URDF gave the J1 axis, the bracket's lowest point, the swept radii
  and the joint limit in minutes. Each of those decided a design choice.
- **A part that hides another part's moving envelope looks fine standing
  still.** Check every new body against the arm rotated to both limits
  before showing it.
- **Tie the arm's load into the drive bracket's bolts.** The steel bracket
  becomes the backing plate, and the bolts go in from below, out of the arm's
  way.
