# 026 — The re-entrancy guard wedged the kiosk for 20 days

| | |
|---|---|
| **Date** | 2026-10-09 |
| **Type** | Permanent wedge in the kiosk's voice-session guard |
| **Status** | ✅ Fixed — immediate (kiosk restart) and root cause (deadlines on every blocking await) |
| **Severity** | High — the robot was completely deaf; nothing in the logs pointed here without the kiosk's own jslog |

---

## Symptom

> "there was livekit supposed to be run here but it's not working anymore"

The wake word fires, the face paints `connecting…`, and nothing else happens.
The last successful LiveKit session was **2026-09-20 16:38** — nineteen days of
silence, while every part of the chain looked healthy:

- LiveKit server: running, port 7880 reachable from the LAN, correct `AAAA`/`A`
  for `<livekit-host>` from the Jetson
- Agent worker: registered and connected to the server
- Jetson: all user services active (wake-word, robot-face, kiosk-firefox, video-player)
- DNS and TCP to the Mac: fine (checked after the morning's stale-route incident
  on another machine on the LAN, which raised that suspicion here too — wrong layer, see below)

## Evidence

The wake-word journal showed the trigger working and the session dying:

```
Okt 09 14:43:40 TRIGGER #1  call  conf=1.00  گردو بابا
Okt 09 14:43:40   session started; mic released, detector paused
Okt 09 14:44:26   stuck on 'connecting' for 45s; giving up and listening again
```

And robot-face's journal had the kiosk's own jslog from the same second:

```
voice-js: voice idle -> connecting
voice-js: joinVoice called; room=present joining=true
voice-js: join already in flight; ignoring
```

`room=present` and `joining=true` on a *fresh* page means an earlier
`joinVoice()` never completed: its `finally` never ran, so the guard was still
set. Every wake since then hit `if (joining) return` and was silently ignored.

## Root cause

In `face.html`, `joinVoice()` sets `joining = true` and clears it in a
`finally` — the finally only runs when the async function settles. Two awaits
inside it had **no deadline**:

- `catch { await room.disconnect(); }` — on a half-open/never-connected room
  this promise can hang forever
- the initial `fetch('/api/voice/wake')` — a hung connection to Flask wedges
  before `room` is even assigned

One failed join (most likely an attempt shortly after the 2026-09-20 16:38
session, when the room was deleted mid-call under the agent worker; the exact
trigger is unconfirmed — the journal had rotated) suspended inside the catch
block on `room.disconnect()`, and the guard stayed set for nineteen days. The
state file froze at `voice: "connecting"` because the kiosk never reached any
`report()` call — so even the wake word's "stuck on connecting for 45s" path
left the panel showing a session that never existed.

Wrong turns, for the record:

- **The Mac's changed IP (stale route, that morning's k3s incident) was the
  first suspect.** Disproven in minutes: the Jetson resolved the hostname
  correctly and reached 7880 fine. The `.37 → .46` DHCP change was real but
  irrelevant to this outage.
- **CPU saturation on the Mac was the second suspect.** The agent worker had
  been flapping `marking as unavailable` around the 0.7 load threshold for
  days. Also real, also irrelevant here: no join ever reached the server.

## Fix

Two layers:

1. **Immediate:** `systemctl --user restart kiosk-firefox.service` — a fresh
   page has `joining = false`, and the first synthetic wake connected end to
   end (face joined in 484 ms, agent job dispatched and initialized in 3.85 s).

2. **Root cause:** every blocking await in the voice path now runs under a
   deadline. `limit()` moved from inside `joinVoice()` (unusable from the
   catch) to module scope, and now wraps:
   - the wake-token fetch (10 s)
   - `room.connect()` (15 s, unchanged)
   - `room.disconnect()` in both the catch and `leaveVoice()` (5 s)

   A wedged disconnect now surfaces as `disconnect timed out after 5000ms` in
   the jslog instead of eating the robot's ears permanently.

Deployed via `./deploy/deploy.sh` + kiosk restart. Verified with a synthetic
`POST /api/voice/wake` from the Jetson:

```
voice idle -> connecting
joinVoice called; room=null joining=false
connecting to ws://<livekit-host>:7880
connected; enabling mic
mic enabled
voice connecting -> listening
```

and the agent log shows the job dispatched and initialized (1.33 s).

## What the wake word should do and doesn't

When it gives up ("stuck on 'connecting' for 45s"), it returns to listening
but leaves `voice: "connecting"` in the state file. Harmless once the kiosk
can clear it, but it means the panel advertised a phantom session for weeks.
Not fixed here; noted so the next reader knows the panel's voice badge can
lie after a failed session.

## Related, unfixed

The Mac's agent worker flaps above the 0.7 load threshold when the machine
is busy (WindowServer, the k3s worker VM, BambuStudio, Spotify were the top
consumers). A wake during an "unavailable" window will connect the kiosk but
no agent will join the room. If that ever bites, either free the CPU or raise
`load_threshold` on the agent.