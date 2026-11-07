# 040 — Drive wheels lost their grip on the new 1st layer

| | |
|---|---|
| **Date** | 2026-10-20 |
| **Type** | Assembly issue: diagnosis + no-reprint fix |
| **Status** | ✅ CAD ruled out · ✅ **Fixed with washers under the motor brackets (2026-11-07)**: the wheels touch, the robot drives · ⏳ Brake when stopped (firmware) |
| **Severity** | Medium: the robot can't drive properly |

---

Follows [033](033-2026-10-17-printing-the-1st-layer-on-the-a1.md) (the print) and [032](032-2026-10-17-measurements-dock-sign-and-arm-mount-angle.md) (caster blocks merged).

## Symptom

After the new 1st layer (`1st-layer-v4`) was assembled, the weight rests on the casters. They sit a little lower than before, and the drive wheels have lost the grip they had on the previous print.

## The CAD hasn't changed

**Measured** in the user's `down-panel`, `-v2` and `-v3`, in `1st-layer-v4` v7 (before the caster merge) and in v11 (printed):

| Feature | All versions |
|---|---|
| Caster mounting face | 28.2 mm below the deck top (x ±19, z ±75…105) |
| Motor bracket pocket floor | 7.0 mm below the deck top, 40 × 44, r2 corners |
| Deck | 10 mm |

**The merge in log 032:** the 3 mm fillets are at the block roots, not on the face the caster screws to.

**So the cause is physical:**
1. **Most likely, a bow in the deck.**
   - The deck printed top-down, 250 mm long, with the caster blocks and sensor pods at both ends.
   - If the ends lifted off the bed during printing, in use they droop. That lowers the casters relative to the wheels at mid-length.
   - On a rigid 4-point base, about 1 mm unloads the drive wheels.
2. **Or a motor bracket isn't seated on its pocket floor:**
   - an insert lip;
   - a burr or support residue;
   - the pocket's r2 corners holding the bracket up.

**Checks:**
1. Lay the plate deck-top-down on glass and look for rocking or end gaps.
2. Check that each bracket sits flat on its pocket floor.

## Fix without reprinting

**Shims between each motor bracket and its pocket floor** lower the wheels.

**Test first:** stacks of M3 washers on the 4 bolts, added until the wheels grip.

**Printed set (`sim/web/tools/plate_motor_shims.json`):**
- 39.4 × 43.4, the pocket minus 0.3 per side, with r2 corners;
- 4 × Ø4 holes on the bracket pattern;
- thicknesses **0.68 / 1.00 / 1.48 / 1.96 mm**, which are whole layer counts at 0.2 + n × 0.16;
- two of each;
- 56 min, 20 g PLA.

**Pick:** the measured gap plus about 0.5 mm. The casters should end up a little high, so the drive wheels always carry the weight.

**Bolts:** with up to 2 mm of shim, the M3×20s still work.
- Outer holes: 8.5 mm into the arm-base foot.
- Inner holes: the tip still clears the nut by about 1 mm.

**Not chosen:** sanding the caster block faces down 1–2 mm. It works too, but it can't be undone and it's harder to keep flat.

## Update (2026-11-07): washers did it

- **What the user did:** washers under the motor brackets, as in "Shims" above, instead of the printed shim set.
- **Result:** turning the wheels by hand, they now carry the robot; driven, the robot moves.
- **Observation:** pushed from behind with the motors off, the robot rolls on its casters, so "the grip is not enough to stop it".
  - **That's expected, not a grip problem.** With the robot idle, firmware 0.5.0 holds both IBT-2 enables low (log 046), so the motors are disconnected and the 1:50 gearboxes back-drive.
  - **The check that tells them apart:** while pushing, watch the wheels or the encoder counts (`ENC`). Wheels turning = back-driving, fine. Wheels standing still while the robot slides = too little grip.
- **To make it hold when stopped:** with EN high and both PWM inputs at 0, the BTS7960 turns both low-side switches on and shorts the motor. That's dynamic braking: it resists pushing, but it doesn't hold on a slope forever. It needs a firmware option ("brake when stopped"); not done yet.

