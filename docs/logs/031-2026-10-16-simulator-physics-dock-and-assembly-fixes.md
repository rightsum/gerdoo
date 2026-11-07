# 031 — A browser simulator, a physics check, the charging dock, and four assembly fixes

| | |
|---|---|
| **Date** | 2026-10-16 (open) |
| **Type** | Design decision + analysis — tipping, torque and traction; the dock; how the covers, display and sensors actually go together |
| **Status** | ✅ Simulator live at <https://rightsum.github.io/gerdoo/> · ✅ Physics model, and two implementations agree · ✅ `charging-dock-v1` modelled, no clashes · ✅ Covers now fixed by radial screws; ultrasonic bosses added · ⚠️ Braking with loaded, outstretched arms can tip it forward: limit the deceleration in firmware |
| **Severity** | Medium. The tipping limit is a real hazard once the arms carry things. The rest is design work. |

---

## 1. The simulator

**Source:** `sim/web/`, published from the `gh-pages` branch.

**Build pipeline:**
1. Every visible body in `gerdoo-assembly-preview` is exported to STL at low refinement, with its world matrix. STL export writes **local** coordinates.
2. `tools/build_assets.py` moves each body into the URDF frame and merges them per group. That frame is X forward, Y left, Z up, with Z = 0 under the wheels.
3. The same script writes `gerdoo.urdf`:
   - a base, two wheels, neck pan/tilt and the lidar
   - two prefixed copies of the ElRobot follower URDF (norma-core, Apache-2.0, license copied into `meshes/elrobot/`)
   - each arm attached with `rpy (0, 0, −π/2)` at `(−42.49, ±145.68, 104.3) mm`
4. `index.html` uses three.js 0.160, urdf-loader 0.12.6 and three-mesh-bvh 0.7.8.

**What it shows:**
- **Sliders:** every joint, labelled with its servo ID (left 1–8, right 11–18).
- **Presets:** rest, reach out, hands up, reach low, hands meet, and wave.
- **Contacts:** mesh-exact, via BVH. Every arm part is checked against the body, the other arm and the floor. A part is not checked against its own arm.
- **Lidar:** 360 rays in the C1's scan plane, against a room plus gerdoo itself. Rays that land on the robot are counted as "blocked".
- **Driving:** differential drive with W A S D or the on-screen pad.
- **Dock state:** charging when the robot is within 4 mm and 3° of the dock.
- **Stability:** a live centre of gravity, the support polygon, and the braking, acceleration and turning limits.
- **Lights:** the KA009 mouth glow, the reactor display, and the kiosk face (amber eyes from `robot-face.js`).

**Arm mount derivation.** The preview places the ElRobot STEP with:
- preview x = −s_y − 111.13
- preview y = s_z + 37.6
- preview z = −s_x + 36.75

The STEP and URDF bases differ by `Rz(90°)` and a `(79.24, 34.55)` mm offset.
The check: the URDF base mesh (±50 × 0..62.5) matches the STEP Base + Base
Shield within 0.2 mm on three edges, and Joint 1 within about 2 mm. Composed,
that gives:

`preview = (−uₓ − 145.68, u_z + 37.6, u_y − 42.49)`

**Verification.** Headless Chrome, `#selftest`:

| Pose | Contacts | Lidar blocked by gerdoo | Brake limit |
|---|---|---|---|
| rest | none | 0° | 0.46 g |
| reach out | none | 0° | 0.40 g |
| hands up | none | **28°** | 0.53 g |
| reach low | none | 0° | 0.50 g |
| hands meet | none | 0° | 0.52 g |
| *test: arm swept inward* | 23 — floors, Jetson, deck, motor, wheel, floor | — | — |
| *test: arms crossed* | 37 — neck, face screen, the other arm | — | — |

The two deliberate crash poses prove the contact check fires. The browser's
centre of gravity matches `tools/physics.py` to the millimetre. Those are two
separate implementations.

## 2. Physics check (`tools/physics.py`)

### Mass model

**Printed parts.** Volume from Fusion × 1.25 g/cm³ × fill factor:
- plates 0.5
- shells 0.9
- bulky parts 0.6

**Bought parts.** Datasheet values where known. The rest are estimates, marked
`~` in the script: the Jetson dev kit, UPS, pack holder, gearmotors and wiring.

**Arms.** The ElRobot URDF inertials: about 547 g per arm.

| | Mass | Centre of gravity (X fwd, Z up) |
|---|---|---|
| Body without arms | 4.42 kg | X −2, Z 123 mm |
| Whole robot, arms at rest | **5.52 kg** | X +19, Z 155 mm |

**Support.** The two wheels sit at Y ±145.65. The casters' swivel axes sit at
X ±90 (the mounts found in `1st-layer-v4`, Body2/3). The support polygon is
therefore a diamond, 180 × 291 mm.

### Results

| Pose | CoG X / Z (mm) | Margin (mm) | Brake limit | Turn limit | J2 torque, left (N·m) |
|---|---|---|---|---|---|
| rest | 19 / 155 | 61 | 0.46 g | 0.75 g | 0.54 |
| rest + 250 g per hand | 43 / 169 | 40 | 0.28 g | 0.45 g | 1.31 |
| reach out | 29 / 151 | 52 | 0.40 g | 0.65 g | 0.84 |
| **reach out + 250 g per hand** | **59 / 164** | **26** | **0.19 g** | 0.31 g | **1.78** |
| hands up + 250 g | −2 / 208 | 75 | 0.44 g | 0.68 g | 0.00 |
| reach low + 250 g | 43 / 126 | 40 | 0.37 g | 0.61 g | 1.31 |
| left arm sideways + 250 g | Y +38 | 49 | 0.36 g | 0.58 g (to the left) | 1.79 |

**Drive.** Torque per wheel (r = 33.15 mm, Crr 0.03):

| Case | Torque per wheel |
|---|---|
| 0.5 m/s² on the flat | 0.07 N·m |
| 0.5 m/s² up a 5° slope | 0.15 N·m |
| 0.3 m/s² up a 10° slope | 0.21 N·m |

- **Top speed** at 160 rpm is 0.56 m/s.
- **Traction:** the centre of gravity sits almost over the axle, so the wheels carry most of the weight. Grip of about 25 N against a 9 N demand is plenty.

### Findings

1. **Braking is the real limit, not static tipping.**
   - Holding 250 g in each hand at full reach, the robot tips forward above 0.19 g, or 1.9 m/s².
   - **Caster trail makes it worse.** The 1" casters' wheels trail about 10 mm behind their pivots.
     - **After driving forward,** the front contact sits at +80 mm instead of +90, so the limit falls to **0.13 g** (1.3 m/s²).
     - **After reversing,** the casters swing out (+100 mm) and the limit is 0.25 g.

     | Pose | Contacts at the pivots | After driving forward | After reversing |
     |---|---|---|---|
     | rest | 0.46 g | 0.40 g | 0.53 g |
     | reach out | 0.40 g | 0.33 g | 0.47 g |
     | reach out + 250 g per hand | 0.19 g | **0.13 g** | 0.25 g |
     | reach low + 250 g per hand | 0.37 g | 0.29 g | 0.45 g |

     The simulator models this live: the casters swivel as you drive, and the support polygon follows their contacts. The browser and `physics.py` agree on every row.
   - **So a hard stop from 0.56 m/s inside about 15 cm would tip it.**
   - **Fix, in the Teensy drive loop:**
     - cap deceleration at 1.0 m/s² normally
     - cap it at 0.5 m/s² when either gripper is beyond 300 mm forward or holding something
     - the e-stop coasts rather than locking the wheels
2. **The casters are close in.**
   - At ±90 mm they give front/back support only 90 mm from the centre, against 145 mm sideways.
   - Moving the front caster out by 20 mm adds about 0.12 g of braking margin.
   - The back caster can't move: the rear ultrasonic pod is in the way.
3. **Shoulder torque.**
   - **Reach out with no load:** J2 needs 0.84 N·m. That is 29% of the STS3215's 2.94 N·m stall, so the 30% default strength cap barely holds the arm out.
   - **With 250 g:** 1.78 N·m, which is 61% of stall.
   - **For long holds:** keep a payload at full reach to about 100 g. Then J2 stays under about 1.2 N·m, roughly 40% of stall.
   - **Rest pose:** J2 needs 0.54 N·m. With about 70% gearbox efficiency that is 0.77 N·m, right at the 0.88 N·m cap. **This explains log 028's "straining at 30%, J2/J3 need ~60%".**
4. **The raised arms blind the lidar.**
   - "Hands up" hides 28° of the C1's scan behind the arms.
   - Navigation should treat those beams as robot, not as obstacles. The simulator marks them red.
   - Or keep the hands below about 340 mm while driving.
5. **Arm-base bolts.**
   - Static moment with one arm sideways plus 250 g: about 2.2 N·m.
   - With a ×3 dynamic factor: 6.6 N·m, inside the 8 N·m design moment of log 029.
6. **Not modelled:**
   - inertial loads from fast arm moves
   - sway of the lidar mast and screen while braking
   - stresses in the floors

## 3. The charging dock — `charging-dock-v1`

Modelled at the docked position in preview coordinates; floor at y −66.7.

### Constraints

| Part | Where it sits (r from the robot centre) |
|---|---|
| Pogo pins | x ±12, 88.7 mm above the floor. They point straight back; tips at r ≈ 132.6 at 6 mm protrusion |
| **Antenna brackets** | out to **r 140** at the back, from 154 mm above the floor |
| Antenna whips | r 123–133, from 160 to 270 mm up |
| Back ultrasonic cans | out to r 129.3, 36–54 mm up |
| Back cover | shell r 128; dock lip r 129.4 at x ±33 |

**Do the antennas interfere?** Yes, with a flat back plate. The brackets stand
about 7 mm proud of the pin tips, so a wall at the pins would meet the
brackets first. The dock avoids that by splitting the height:

### Design

| Part | What it does |
|---|---|
| **Cradle**, 110 mm tall | Concave face at r 131 over ±45°. Its top is 44 mm below the antenna brackets |
| **Contact plates** | Two 14 × 26 × 1 copper plates in flat pockets at x ±12. Each takes 2 M3 screws through to the hollow inside, where the ring terminals go |
| **Stop pads** | At 180 ± 38°, r 128.6. The cover shell stops on them, clear of the gill vents. This sets the docking position, so the pins don't have to |
| **Presence-switch pocket** | For a KW11 microswitch at the bottom centre. The plates go live only while the robot presses it |
| **DC-022B input** | On the back wall, for the 19 V supply |
| **Lidar fin** | Separate print, 200 wide. Its face is at r 160, which is 20 mm behind the brackets and 27 mm behind the whips |
| **Fin signature** | A 90° V-notch, 120 wide, at the C1's scan height (y 280–350). It gives the docking routine a unique lidar shape to find and centre on |

**Clash check (boolean, 0 mm³):**
- cradle and fin against every robot body
- the back pod clears the cradle by 1.7 mm

**Pin setting:** at the stop pads, the plates are about 2.6 mm in front of a pin
tip that protrudes 6 mm. Push the pins in until the tips stand 1–1.5 mm past
the plate position at docking, i.e. about 4.5 mm beyond the dock lip, then
glue them.

**Weight:**
- Solid: 1.6 kg cradle and 1.8 kg fin. Print at 15% infill.
- Put steel washers or sand in the cradle cavity, and fit rubber feet.
- At 15% infill, the robot's push (2 pins at about 1 N, plus 6 kg rolling in at under 0.05 m/s) is far below what moves the dock.

**Safety:**
- The plates are exposed and live at 19 V when powered. That is why the presence switch is there.
- On the robot side, keep the DC-022B's switch pin (or one Schottky per input), so the jack can never back-feed the pogo pins.

## 4. Assembly fixes

**Front cover screws (the user's catch).**
- **The problem:** the bottom tab at 0° was unreachable once the 2nd floor is on. All three bottom tabs would have needed a driver from above, through the floor.
- **The fix:** both covers now fasten with **radial M3 button-head screws from the outside**, used as visible "rivets". Each counterbore is 6.5 × 1. They go into M3 heat-set inserts (Ø4.2 × 6) pressed radially into the 10 mm floor edges.

| Cover | Into | Angles | Height (y) |
|---|---|---|---|
| Front | 3rd floor edge | ±23° (inside the chamfered top corners) | 166 |
| Front | 2nd floor edge | ±30° (clear of the T1 trunks) | 82 |
| Front | deck edge | ±18° | −5 |
| Back | 2nd floor edge | 180 ± 30° | 81.5 |
| Back | deck edge | 180 ± 20° | −5 |

- Both covers now reach y −10, so the deck-edge screws have material around them.
- The back cover now reaches y 86, overlapping the 2nd floor edge and stopping 1 mm under the antenna brackets.
- The tabs and their vertical inserts are deleted.
- Every insert was checked: hole open, plastic above and below.

**Ultrasonic boards (the user's catch).**
- **The problem:** they were only slid in.
- **The fix:** each pod now has 4 bosses, Ø4.5 × 9 mm, with M2 self-tap pilots (Ø1.7 × 5) on **42 × 17**. The bosses reach where the board sits, 12 mm behind the can faces.
- ⚠️ The 42 × 17 pattern is one forum caliper measurement ([SparkFun](https://community.sparkfun.com/t/attaching-a-ultrasound-hc-sr04-unit/32443)), and clones vary. **Measure the board.**

**Display in the reactor (the user's question).** It goes in from behind, on the bench, with the cover off the robot:
1. Screw the printed retainer onto the display's 4 brass standoffs (4× M2×4).
2. Drop the display and retainer, glass first, into the pocket from inside the cup. The glass stops on the bevelled lip.
3. Fix the retainer's two ears to the posts with 2× M2×6 self-tap. The posts sit 0.2 mm short, so tightening presses the glass into the lip.
4. Lay the mic ring in the cup, plain side to the cover. Its 52.5 mm hole passes around the retainer, whose corners are at r 24.4.
5. Screw the ring down with 3× M3×6 self-tap at 12, 4 and 8 o'clock.
6. Plug in the display's GH cable, which runs back through the ring opening. Plug the ring's FPC into the core board on the 2nd floor, through the bottom notch and along the 19 × 1.5 channel.
7. Fit the cover to the robot with its 6 rivet screws.

**Speaker (the user's question).**
- It hangs **under the 3rd floor, cone up**, on 4 M3 inserts on the measured 43.4 square.
- It fires into a Ø46 × 8 chamber with a 2 mm grille skin: 85 × Ø3.2 holes, 49% open.
- A honeycomb cap sits on top: 97 cells, 3.2 mm, held by 3 press pins.
- The first version used a 10 mm-thick grille with tiny offset cap holes, which would have muffled it.

## Wrong turns

- **Editing the back cover's silhouette sketch in place.**
  - Fusion kept a stale profile reference (`InternalValidationError: curProfile`), and a failed script left the timeline rolled back.
  - **What worked:** delete that cut, apply the same sketch as a new trim at the end of the timeline, then redo the edge fillet.
- **Bottom tabs for the covers.** They looked fine in the model, but nobody could reach the 0° screw. Check where the screwdriver goes.
- **`saveAs` for `3rd-floor-v2` "never reached the cloud".** It had, much later. The upload is asynchronous: check `isSaved` some minutes later before calling it lost.

## Next

1. **Firmware:**
   - deceleration cap, 1.0 / 0.5 m/s², with the e-stop set to coast
   - strength ≥ 60% for J2 and J3
2. **Measure:**
   - the HC-SR04P hole pattern
   - the pogo pin travel
   - the real masses of the Jetson, the UPS with its cells, and the gearmotors
3. **Dock wiring:** microswitch in series with one plate, on the dock's 19 V side.
4. **Docking routine:** find the fin's V in the scan, then back in at ≤ 0.05 m/s and stop on the charge current.
5. **Simulator:** add an arm self-collision check. Caster trail is done.
6. **Casters:**
   - Measure their offset; the simulator assumes 10 mm.
   - Measure their height: the listing's 37.8 mm is 1.3 mm more than the gap under the caster blocks (36.5 mm to the tyre contact). If both numbers are right, the casters lift the drive wheels off part of their load. Check the drive wheels press on the floor before printing the final blocks.

## Takeaways

- **Check how each fastener is reached as well as where it sits.** If the
  screwdriver can't get to it, it's a design bug.
- **Validate a model against something already seen.** The torque model
  reproduced log 028's 30%-strength strain. That's what makes the tipping
  numbers believable.
- **The highest thing on the back sets the dock's shape,** and here that was
  the antennas, not the contacts.
