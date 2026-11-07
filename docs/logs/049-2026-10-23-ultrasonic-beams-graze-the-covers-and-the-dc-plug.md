# 049 — The inner ultrasonic beams graze the covers; the DC plug that wouldn't seat

| | |
|---|---|
| **Date** | 2026-10-23 |
| **Type** | Design check + hardware note |
| **Status** | ✅ Clash measured · ✅ Decision: handle it in software · ⏳ Software filter not written · ✅ Plug size noted in `inventory.md` |
| **Severity** | Low |

---

Written on 2026-11-07 from the session transcript. Log 046 said "Log 034/042 already found that the inner beams graze it", but neither of those logs has it. This is the entry it meant.

## 1. Ultrasonic beam cones against the covers

**The check:** each HC-SR04P beam was modelled as a cone tilted 8° up and 20° out, and intersected with the covers and the deck in the assembly preview.

| Sensors | Cone half-angle | Overlap |
|---|---|---|
| Inner pair (x ±52) | ±7.5° | 1 mm³ of the cover's bottom edge |
| | ±10° | 10 mm³ |
| | ±15° | 46 mm³ of the cover + 8 mm³ of the deck rim, from 10–12 mm in front of the face |
| Outer pair (x ±77) | up to ±15° | clear |

**Options:**
- 24 × 5 mm arches cut into the covers' bottom edge.
- Software: ignore echoes below a minimum range.

**Decision:** software. The user: "the cover is being printed".

**The plan, not yet written:**
- minimum range 4 cm;
- median of 5 readings;
- staggered firing (done in 0.5.0, log 046);
- a self-check at boot that flags a sensor stuck on a near echo.

**Evidence it matters:** on 2026-10-28 FL read a steady 12.8 cm and BR jumped around (log 046). On 2026-10-29 FR read 3.6 cm and BR 6.1 cm with nothing in front. On 2026-11-06 back-right read 3.6 cm.

## 2. The DC plug didn't go fully into the jack

- The user's 19–20 V laptop-style supply is fine for the robot's input.
- **A 5.5 × 2.1 mm plug in a 5.5 × 2.5 mm jack** jams on the wider pin and only touches it at the tip: an intermittent contact under load.
- Use a 5.5 × 2.5 plug. This was noted in `inventory.md` ("2.1 ≠ 2.5").
- **2026-11-06:** the 90 W LEICKE supply was chosen partly because it ships a dedicated 5.5 × 2.5 tip (log 056).

## Takeaways

- Check sensor beams against the bodywork in CAD before the bodywork is printed. It's a two-minute boolean.
- Barrel plugs: check the inner diameter, not just the 5.5 mm outer one.
