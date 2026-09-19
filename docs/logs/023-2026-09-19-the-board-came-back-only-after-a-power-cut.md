# 023 — The board came back only after a power cut, and I still cannot say why it left

| | |
|---|---|
| **Date** | 2026-09-19 |
| **Type** | Fault (unresolved cause) + recovery + instrumentation gaps found |
| **Status** | ✅ Hardware recovered and verified · ❌ Root cause unknown · ⏳ Nothing yet prevents recurrence |
| **Severity** | Microphones and touchscreen both dead; the robot could neither hear nor be touched |

---

## What happened, in order

A reboot was performed to clear the aftermath of the journald flood in log 021.
After it:

1. A crash dialog on screen — a **stale** report for `systemd-journald` from
   08:40, fallout from the flood, not a new fault. Dismissible.
2. The display came up **portrait**. `rotate-display.sh` failed with
   `Permission denied`.
3. The microphones were **completely dead** — worse than the deafness of
   log 022.
4. The touchscreen was **absent from `lsusb` entirely**, and X listed no
   pointer devices at all.

Only a full power cut of the reSpeaker board — USB-C **and** the 12 V terminal —
brought either of them back. A host reboot did not.

## The rotation fault, and the durable cause behind it

`rotate-display.sh` was not executable on the robot. `chmod +x` fixed the
immediate symptom, and `xrandr` then reported the panel `1920x1080+0+0 right`.

The real cause is one layer down and would have come back on every deploy: git
had the file recorded as **100644**, and `rsync` faithfully copies the mode it
finds. Three scripts were affected, including the `gerdoo-audio-repair.sh`
watchdog added the same day — which would have been silently non-executable on
arrival.

```bash
git update-index --chmod=+x wake-word/gerdoo-audio-repair.sh \
                            robot-face/deploy/rotate-display.sh \
                            robot-face/deploy/run-lidar.sh
```

**Takeaway: a deploy that copies file modes makes the git index part of the
runtime contract.** A script's mode is not cosmetic metadata; it is whether the
thing runs at all.

## The hardware fault

### What was measured while it was broken

| Evidence | Reading |
|---|---|
| All six mic channels | peak **4–5** — digital silence |
| The four **raw** channels | also 4–5 |
| Board enumeration | present |
| Audio playback | working |
| Control commands (`xvf_host`) | answered |
| Touchscreen in `lsusb` | **absent** |
| X pointer devices | none but the virtual ones |

The raw channels are the decisive part. They bypass echo cancellation,
beamforming, noise suppression and automatic gain control entirely. **No driver,
no PulseAudio module and no DSP setting can drive them to zero.** That put the
fault below every layer of software — a live firmware with a dead microphone
front end.

### Why "power or hub", and not the flex cable

Two independent devices failed in the same session, and the USB topology says
they share a parent:

```
1-2        Realtek 4-port hub
 ├─ 1-2.1      nested hub
 │   └─ 1-2.1.1   touchscreen controller   (64 mA)
 ├─ 1-2.2      UART bridge
 ├─ 1-2.3      reSpeaker XVF3800           (400 mA declared, plus a class-D amp on 12 V)
 └─ 1-2.4      Teensy
```

Different branches, one hub. And the bad state **survived a host reboot** but
not a power cut, so it lived somewhere a reboot does not reach: the board's own
power domain, or the hub. A flex cable working itself loose explains the
microphones; it does not explain a touchscreen on another branch vanishing at
the same time, nor does it explain recovery by power cycling a different device.

### The recovery, verified

After the power cut, all three failures cleared together:

- the array re-enumerated with all six USB interfaces present again (while
  broken, its descriptor had also been incomplete),
- the touchscreen returned and X saw it as a pointer device,
- `gerdoo_mic` was rebuilt **by the watchdog from log 022, unprompted**, which
  logged the whole sequence:

```
gerdoo_mic could NOT be rebuilt — is the board enumerated?    (board unplugged)
gerdoo_mic missing — rebuilding
gerdoo_mic rebuilt                                            (board back)
```

The microphones were then proven alive by playing a 440 Hz tone at two speaker
volumes and measuring every channel — a test that needs no human in the room:

| channel | silent room | tone at −9 dB | tone at max |
|---|---|---|---|
| ch2 (raw) | rms 2 | rms 29 | **rms 84** |
| ch3 (raw) | rms 2 | rms 7 | rms 37 |
| ch4 (raw) | rms 1 | rms 20 | rms 57 |
| ch5 (raw) | rms 2 | rms 29 | **rms 84** |
| ch0 (processed) | rms 5 | rms 5 | rms 14 |

Two things fall out of one measurement. The raw microphones **scale with speaker
output**, so they hear. And ch0 stays near the floor **while the speaker is
blaring**, so the hardware echo canceller is subtracting the robot's own voice —
the property the whole XVF3800 migration was for.

**Takeaway: when a symptom is "it hears nothing", the test is a sound you
control, not a person speaking.** Ambient level cannot distinguish a dead
microphone from a quiet room; a tone at two known volumes distinguishes both at
once.

## Decision: the speaker goes to maximum, and why the old setting was partly fiction

The owner asked for maximum volume. The setting was 85%, defended by a comment
claiming that at full output the canceller cannot keep up and the agent
transcribes itself.

Reading the actual controls showed that claim had never been in force:

| control | value |
|---|---|
| `PCM,0` (left/right) | 60/60 — **0 dB** |
| `PCM,1` (mono master) | 51/60 — −9 dB |
| `Headset` capture, all 6 | 60/60 |

PulseAudio drives `PCM,0` to 100% on its own whenever it sets sink volume, so
`SPK_LEVEL` only ever held back `PCM,1`. The system had been running at
"85%" that was really one control at full and one at −9 dB.

Both are now at 0 dB, and `SPK_LEVEL` defaults to `100%` so the watchdog stops
undoing it on every rebuild. The comment was rewritten to say what is actually
known: the shipped 67% is −20 dB and sounds broken (certain, from log 018), and
the self-transcription risk at full output was **never measured against a real
call**. If the agent starts hearing itself, this is the first knob to lower.

**Takeaway: a setting that a second component silently overrides is not a
setting.** The 85% was documented, committed, and inert on half the signal path.

## Instruments found broken while investigating

Three, none of which announced themselves:

**1. `journalctl --user` returns "No journal files were found."**
`/var/log/journal` does not exist, so journald is volatile-only and the user
instance cannot read the system's. The logs *do* exist — reachable as
`journalctl _SYSTEMD_USER_UNIT=wake-word.service` — but every user-service log
dies on reboot. `sudo mkdir -p /var/log/journal` makes them persistent.

**2. Kernel messages are unreadable by any route.** `ReadKMsg=no` (log 021)
stopped journald ingesting them — correctly, that is what ended the 97% CPU
burn. But `kernel.dmesg_restrict=1` also blocks `dmesg` for a non-root user, so
the `xhci` errors behind this whole class of fault cannot be seen at all. The
right compromise keeps `ReadKMsg=no` and sets `kernel.dmesg_restrict=0`, so the
ring buffer can be polled on demand without journald ingesting a flood.

**3. Battery telemetry has been dead for sixteen days.** `/api/battery` returns
500 with `NameError: name 'BATTERY_FILE' is not defined`; the constant was
deleted on 2026-09-03 in `39905cb`, while the handler that reads it was left
behind. `battery-bridge.service` is enabled but **inactive**, and
`/tmp/battery_status.json` does not exist. The control panel's battery bars have
been silently blank — `pollBattery()` swallows the error in an empty `catch {}`.

That third one matters more than it looks: the leading hypothesis for this
fault is a marginal power rail, and **the instrument that would test it has
been broken the whole time.**

## What prevents this happening again: nothing

Said plainly, because the opposite is easy to imply. The watchdog from log 022
heals `gerdoo_mic` and proved itself again today, unprompted. It cannot revive
dead hardware, and it has nothing to say about a touchscreen.

The cause has now been treated twice and diagnosed zero times.

There is also a risk taken knowingly: **raising the speaker to maximum increases
amp draw on the 12 V rail.** If the fault is power, today's change makes it more
likely, not less.

## The four instruments this needs

1. **A re-enumeration log** — a udev rule appending a timestamp and device
   number for the array and the touchscreen. Today's only evidence of churn was
   indirect: the array held `devnum=19` while every other device on the bus sat
   between 2 and 11, meaning it had burned roughly eight enumerations since
   boot. A rate is worth more than an anecdote. (Sampled every 20 s for three
   minutes afterwards: stable. Three minutes proves three minutes.)
2. **A microphone liveness canary** — the watchdog already wakes every 30 s;
   have it sample raw-channel peaks and log them, so the moment the microphones
   die is timestamped rather than discovered hours later by a human noticing the
   robot is ignoring them.
3. **Kernel visibility** — `sudo sysctl -w kernel.dmesg_restrict=0`.
4. **Battery telemetry restored** — fix the endpoint, start the bridge, and keep
   a voltage series to test the brownout hypothesis, especially now that the amp
   runs louder.

## Takeaways

- **A fault that survives a reboot but not a power cut is not in your
  software.** That single distinction moved this from "which service broke" to
  "which power domain latched".
- **Raw, unprocessed channels are the ground truth in an audio stack.** Every
  processed measurement is downstream of something that could explain the
  reading away.
- **Check whether a setting is actually in force, not merely configured.** Two
  controls, one silently overridden, and the documented value was fiction.
- **Count what you cannot see.** Three separate instruments — kernel log, user
  journal, battery voltage — were all unavailable, and each absence was
  discovered only by needing it mid-investigation.
- **Say "nothing prevents this" when nothing prevents it.** A self-healing
  watchdog reads like a fix and is not one.

## Related

- [021](021-2026-09-19-kiosk-page-took-the-robot-down.md) — where `ReadKMsg=no`
  came from
- [022](022-2026-09-19-the-robot-went-deaf-silently.md) — the watchdog that
  healed the microphone here, and the six wrong theories before it
- [018](018-2026-09-15-xvf3800-hardware-aec.md) — the two playback controls and
  the hidden −20 dB
