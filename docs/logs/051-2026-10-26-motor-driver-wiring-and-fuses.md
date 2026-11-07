# 051 — Motor-driver wiring and the fuse on the servo feed

| | |
|---|---|
| **Date** | 2026-10-26 |
| **Type** | Wiring |
| **Status** | ✅ IBT-2 pins in `inventory.md` (final map 2026-10-27) · ⚠️ Servo-feed fuse: 30 A fitted, 15 A advised · ⏳ Fuse colours to check before closing the floor |
| **Severity** | Medium (fuse too large for the wire) |

---

Written on 2026-11-07 from the session transcript.

## IBT-2 (BTS7960) wiring

| Signal | Left driver | Right driver |
|---|---|---|
| RPWM / LPWM | 5 / 6 | 22 / 23 |
| R_EN + L_EN (joined) | 7 | 8, **moved to 21 on 2026-10-27** |
| VCC | 3.3 V | 3.3 V |
| R_IS / L_IS | not connected | not connected |
| Encoder A / B | 30 / 31 | 0 / 1 |

At VCC = 3.3 V the 74HC buffer's threshold is 2.31 V, which the Teensy clears (inventory). The full pin map is in `inventory.md` (2026-10-27) and was used for firmware 0.5.0 (log 046).

## Fuses

**Found:** the user had a **green 30 A fuse on the feed to all 18 servos**.

**Advised:**

| Branch | Fuse |
|---|---|
| Servo feed (18 × STS3215) | **15 A, blue** |
| Each drive motor | 20 A, yellow |
| Power-pack main | 30 A, green |
| Electronics pack | 5 A, tan |

A fuse protects the wire, so it must blow below what the thinnest wire on that branch can carry. 30 A on the servo trunk wouldn't blow before the trunk overheated.

**Still to do:** check every fuse's colour before the floor is closed. This is on the pre-close checklist.
