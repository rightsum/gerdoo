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
| [010](010-2026-08-04-gesture-detection-and-gpu-evaluation.md) | 2026-08-04 | Hand gesture detection + tracking, and a GPU acceleration evaluation | ✅ CPU shipped · ⏸️ GPU deferred |
| [011](011-2026-08-19-charger-stepdown-voltage-test.md) | 2026-08-19/20 | 19V charger → step-down → 3S battery charging, battery monitoring, neck servos, fist tracking | ✅ Charging tested · 🔄 Servo replacement pending |
| [012](012-2026-08-26-led-strip-ambient-brightness.md) | 2026-08-23/26 | COB LED strip on a D4184 MOSFET, ambient brightness from a photoresistor, Teensy flashing fixes | ✅ Working · 🔄 Fuse + current measurement pending |
| [013](013-2026-08-29-audio-and-persian-wake-word.md) | 2026-08-29/30 | USB speaker output, and a Persian wake word ("Gerdoo, baba") via grammar-restricted Vosk | 🔄 Working, tuning false positives · range ~4 m |
| [014](014-2026-09-01-livekit-voice-agent.md) | 2026-08-30→09-01 | LiveKit voice agent — wake word to real conversation, and the audio-device problems behind it | ✅ Working · 🔄 AEC marginal across two USB clocks |
| [015](015-2026-09-02-voice-switch-echo-and-language.md) | 2026-09-02 | Voice on/off switch, wake-word false positives, echo filtering that made barge-in usable, selectable recognition language | ✅ Working |
| [016](016-2026-09-02-agent-tools-search-and-time.md) | 2026-09-02 | Agent tools — web search and a clock with the Persian calendar, so it can answer about the outside world | ✅ Working |
| [017](017-2026-09-03-face-tracking.md) | 2026-09-03 | The neck follows your face during a call, replacing gesture detection — and three definitions of "centre" that disagreed | ✅ Working |
| [018](018-2026-09-15-xvf3800-hardware-aec.md) | 2026-09-15 | reSpeaker XVF3800 becomes the robot's mic and speaker — hardware echo cancellation, every software echo workaround removed, a hidden -20 dB volume control | ✅ Deployed · 🔄 Barge-in and wake-word range to re-test |
| [019](019-2026-09-18-video-playback.md) | 2026-09-18 | YouTube video playback on the kiosk screen — mpv + yt-dlp over JSON IPC, a call takes the screen and video resumes after, a Persian stop phrase | ✅ Deployed — see 020 |
| [020](020-2026-09-18-video-playback-deployed.md) | 2026-09-18 | Deploying it: the search that answered early and exited late, a microphone source that vanished silently, an agent answering before the question ended — and six wrong theories about a deaf microphone | ✅ Playback working · ⏳ Wake word during loud playback unresolved |
| [021](021-2026-09-19-kiosk-page-took-the-robot-down.md) | 2026-09-19 | The kiosk page took the robot down twice — a `fetch` whose rejection was logged by fetching again, 1019 threads, 1024 descriptors and an accept storm | ✅ Fixed and deployed · 🔄 Watching for recurrence |
| [022](022-2026-09-19-the-robot-went-deaf-silently.md) | 2026-09-19 | The robot went deaf and every service said it was fine — a re-enumerating board, a detector left on the raw six-channel downmix, and a 30-second watchdog that heals it | ✅ Self-heal proven · ⏳ USB instability unexplained |
| [023](023-2026-09-19-the-board-came-back-only-after-a-power-cut.md) | 2026-09-19 | Microphones and touchscreen both dead, recovered only by cutting power — a fault below every layer of software, a speaker setting that was never in force, and three instruments found broken | ✅ Recovered and verified · ❌ Cause unknown |
| [024](024-2026-09-19-the-wake-word-was-working-the-whole-time.md) | 2026-09-19 | Ten shouts and no answer — the first one woke it, the music it never paused drowned the reply, and the echo canceller that was blamed measured 38.5 dB | 🔄 Cause found; the "fix" was redundant and reverted (see the correction) |
| [025](025-2026-09-19-the-speaker-drowns-the-wake-word.md) | 2026-09-19 | At 90% the music masks the voice at the microphone itself — proven on the raw uncancelled mic — plus a touch "Wake!" button, and a window manager that will not let it show over video | ✅ Cause proven · ✅ Touch controls drawn inside mpv, over fullscreen video · ❌ Wake at volume unsolved |
| [026](026-2026-10-09-the-reentrancy-guard-wedged-the-kiosk.md) | 2026-10-09 | The re-entrancy guard wedged the kiosk for 20 days — one unbounded `room.disconnect()` in a catch block, and every later wake silently ignored | ✅ Fixed and deployed |
| [027](027-2026-10-13-arm-cameras-on-the-panel.md) | 2026-10-13 | Arm cameras on the panel — two OV9281s sharing serial `SN0001`, one that only runs at 210 fps, and a single V4L2 buffer that ate 40 % of its frames | ✅ Working and deployed · ✅ Left camera reflashed to the right camera's 2024 firmware, now 30 fps · ❌ `quirks=128` found useless for MJPEG |
| [028](028-2026-10-15-both-arms-on-the-servo-bus.md) | 2026-10-15/16 | Both arms on the servo bus: the board's A/B jumper, a whole chain still at factory ID 1, assigning 16 IDs on assembled arms, and the first moves straining against a 30% torque cap and the 0/4095 seam | ✅ IDs, panel, multi-turn mode on all 16 servos · 🔄 Right arm and gripper calibration |

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
