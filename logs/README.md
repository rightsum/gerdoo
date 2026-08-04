# Engineering log

One file per problem. What broke, what the evidence said, what fixed it, how it was verified.

## Naming

```
NNN-YYYY-MM-DD-short-title.md
```

`NNN` = sequential, never reused. Date = when the issue was **resolved** (or opened, if still open — say which in the header).

## Index

| # | Date | Title | Status |
|---|---|---|---|
| [001](001-2026-08-04-jetson-wifi-unreachable.md) | 2026-08-04 | Jetson unreachable over wifi — Realtek power save | ✅ Fixed |
| [002](002-2026-08-04-usb-topology-and-peripheral-split.md) | 2026-08-04 | USB topology, powered hub, Teensy/Jetson peripheral split | ✅ Decided |
| [003](003-2026-08-04-teensy-rawhid-bringup.md) | 2026-08-04 | Teensy bring-up — RawHID mode, headless flashing, unstable port | ✅ Fixed |
| [004](004-2026-08-04-rplidar-c1-bringup.md) | 2026-08-04 | RPLIDAR C1 bring-up on Jetson USB — first light, 10 Hz | ✅ Working |
| [005](005-2026-08-04-headless-teensy-flashing.md) | 2026-08-04 | Headless Teensy flashing — `teensy_loader_cli`, GUI dependency removed | ✅ Done |
| [006](006-2026-08-04-robot-face-adoption.md) | 2026-08-04 | Adopting the `robot-face` kiosk into this repo | ✅ Adopted |
| [007](007-2026-08-04-microros-bringup.md) | 2026-08-04 | micro-ROS on Teensy — Dual Serial, console preserved, reconnect | ✅ Working |
| [008](008-2026-08-04-control-panel-camera-lidar.md) | 2026-08-04 | Control panel — authenticated camera stream + live LiDAR view | ✅ Deployed |
| [009](009-2026-08-04-lidar-motor-kept-spinning.md) | 2026-08-04 | LiDAR motor kept spinning after the service stopped | ✅ Fixed |

Entries are either **problems** (001, 003) or **design decision records** (002). Both belong here — a decision you cannot reconstruct the reasoning for is as expensive as a bug you cannot reproduce.

## What goes in an entry

- **Symptom** — the exact error, quoted
- **Evidence** — commands run and what they returned, including tests that ruled things *out*
- **Wrong turns** — record them; a wrong guess documented once is a wrong guess not repeated
- **Root cause** — the actual mechanism, not the workaround
- **Fix** — exact commands
- **Verification** — measured proof, and honesty about what the proof does *not* cover
- **Takeaways** — the generalisable rule

## Related

- [`../ACTION-PLAN.md`](../ACTION-PLAN.md) — scheduled follow-ups
- [`../inventory.md`](../inventory.md) — hardware reference and wiring truth
