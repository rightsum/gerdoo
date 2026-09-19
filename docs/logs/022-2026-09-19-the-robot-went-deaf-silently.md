# 022 — The robot went deaf, and every service said it was fine

| | |
|---|---|
| **Date** | 2026-09-19 |
| **Type** | Fault + self-healing fix |
| **Status** | ✅ Self-heal deployed and proven · ⏳ Underlying USB instability unexplained |
| **Severity** | The wake word stopped working entirely, with no error anywhere |

---

## Symptom

"گردو بابا" stopped waking the robot. Not intermittently — completely. Meanwhile:

- `wake-word.service` — **active**
- the microphone — **present, unmuted, every gain at maximum**
- the audio — **clean, no dropouts, sensible level**
- the call path — **working** (a wake forced through the API connected, and the
  agent transcribed Persian speech correctly)
- the recogniser — **working** (saved recordings of the phrase still matched at
  confidence 1.00, including one from that morning)

Every part reported health, and the robot could not hear its name.

## Root cause

The XVF3800 re-enumerated on USB **four times in one afternoon** — device 019 →
034 → 038 → 044. Each time, PulseAudio destroyed `gerdoo_mic`, the remapped
source carrying the board's **processed** channel.

The wake-word detector holds its capture stream open across that. It does not
die, and it does not reconnect to the right thing: it ends up on the **raw
six-channel input**, which PulseAudio then downmixes to mono for it — averaging
the one good processed channel together with four un-cancelled microphones.

That produces audio which is:

- structurally intact (no dropped chunks),
- at a plausible level (rms in the hundreds),
- with every gain in the chain at maximum,
- and roughly **four times too quiet to recognise**.

Measured side by side:

| | what the detector received | a recording that did trigger |
|---|---|---|
| loudest second | rms 611 | **rms 13,258** |
| seconds above speech level | 6 of 60 | 2 of 3 |

Five minutes of the owner speaking decoded to a single filler word.

**The silence of the failure is the point.** No service failed, no log line was
written, no counter incremented. The one observable difference was which source
id appeared in `pactl list source-outputs`, and nothing was watching it.

It also vanished **twice with no USB event at all** — PulseAudio dropped the
module on its own — which rules out a udev-only fix.

## The fix

Two mechanisms, because either alone misses half the cases:

| Piece | Catches |
|---|---|
| `gerdoo-audio-repair.timer` — every 30s | the silent case, where the module disappears with no device event |
| `99-respeaker-xvf3800.rules` → `SYSTEMD_USER_WANTS` | the loud case, immediately on re-enumeration |

Both trigger the same idempotent script, `gerdoo-audio-repair.sh`, which:

1. rebuilds `gerdoo_mic` via `audio-setup.sh` if it is missing,
2. compares the detector's actual source id against it,
3. restarts the detector only if they differ,
4. **defers if a call is live** — a conversation is worth more than a fast
   repair, and the next tick is thirty seconds away,
5. writes nothing and changes nothing when healthy, so it is safe to run forever.

udev cannot do step 1 itself: it runs as root with no access to the user's
PulseAudio session. `SYSTEMD_USER_WANTS` hands the work to the session that can.

## Verification

The failure was reproduced deliberately — unloading the remap module is exactly
what a re-enumeration does:

```
  gerdoo_mic now: 0            (broken, as after a re-enumeration)
  detector fell onto source 53 (the raw six-channel input — the real failure)
  +5s   still missing
  ...
  +30s  gerdoo_mic back (source 55), detector on source 55 — REATTACHED
```

```
16:21:22 gerdoo_mic missing — rebuilding
16:21:22 gerdoo_mic rebuilt
```

And a recording made through the repaired path, with music playing for the middle
third, measured rms 2,625 speaking alone and **rms 2,625 speaking over the
music** — the echo cancellation removing the robot's own output so completely
that the level did not move.

## Wrong turns — a long list, and worth keeping

Six explanations were proposed before the real one, and the measurements that
killed several of them were themselves broken:

| Theory | Reality |
|---|---|
| The room had become too quiet; the array had been physically moved | It was a six-channel downmix |
| The board's beam selector was starved of speech energy | The zeros were measured **against a paused player** |
| Automatic gain control was ducking the near end | `PP_AGCGAIN` was pinned at maximum in both conditions |
| Beam gating was silencing inactive beams | `AEC_FIXEDBEAMSGATING` was 0 — gating was off |
| The USB stream was shredding the audio | 0.2 level discontinuities per second; the audio was clean |
| Capture gain had been reset by the re-enumeration | Every gain read 100% / 0 dB |

And the instruments that failed, each in a way that produced confident nonsense:

- **Twice** a measurement was taken against a player that had been left paused by
  an earlier test, and "music playing" was captured against silence.
- An isolation experiment sampled the wrong process — `pgrep` immediately after a
  restart matched something that was not the app, and every sample read "4 file
  descriptors", which is impossible for a live server.
- A comparison of the processed channel against the raw microphones measured the
  **automatic gain control**, not the echo canceller.
- A live gain probe parsed the control tool's debug output as data, and every
  sample came back byte-identical for eighteen seconds.
- A recording test swallowed `parecord`'s stderr, so an empty 44-byte file looked
  like a quiet room rather than `Stream error: No such entity`.

The last one is what finally exposed the real fault: asking to hear the raw
recording, rather than trusting a derived number.

## Takeaways

- **"Active" is not "working".** Every service reported healthy throughout, twice
  over: here, and in the outage in log 021.
- **A process that holds a handle across a device disappearing is not
  reconnected — it is misconnected.** Nothing reports that, because from the
  process's point of view the read still succeeds.
- **Derived metrics hide faults that raw data exposes.** Level, structure and
  gain readings all looked plausible. Listening to the recording found the
  problem in one attempt.
- **When an instrument disagrees with a symptom, suspect the instrument.** Half
  the measurements in this investigation were void, and each void one cost a
  wrong conclusion handed over with confidence.
- **Self-healing beats diagnosis for a fault that recurs.** This one returned
  four times in an afternoon; the watchdog resolves it in thirty seconds without
  anyone noticing.

## Still open

- **Why the board re-enumerates at all.** It sits behind a powered hub
  (`1-2.3`); the controller logs thousands of `buffer overrun` warnings per
  second for its audio endpoint, and moving it to a port directly on the Jetson
  has not yet been achieved. The watchdog treats the symptom, not this.
- **Kernel messages are no longer recorded** (`ReadKMsg=no`, see log 021), so the
  overrun rate can no longer be observed from the journal. Reverse that setting
  before investigating the USB fault.
