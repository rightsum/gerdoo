# 024 — The wake word was working the whole time

| | |
|---|---|
| **Date** | 2026-09-19 |
| **Type** | Misdiagnosis, then a real design gap |
| **Status** | ✅ Fixed and deployed · 🔄 Barge-in during a call still unmeasured |
| **Severity** | Routine — but three hours were spent on the wrong component |

---

## Symptom

> "now the music is playing i shouted gerdoo baba like 10 times but none detected!!"

Reported as an echo-cancellation failure. The XVF3800 was suspected, and the whole
investigation started from there.

## What was actually wrong

**Nothing, in the audio path. The first shout was detected, and the detector then
stopped listening on purpose.**

```
21:15:18  TRIGGER #2  call  conf=1.00  گردو بابا
21:15:18  session started; mic released, detector paused
21:16:10  session ended; mic reacquired, listening again
```

52 seconds deaf, by design — the microphone is released so the browser can have it
for the LiveKit call. Shouts 2 through 5 arrived during that window and were never
heard by anything.

The owner could not tell a session had started, because **the music kept playing
through it.** `wake_word.py` only stopped a video for the `stop` action
(`گردو بسه`); on a `call` it left playback running. So the chime, the agent's
greeting and the whole conversation came out of the same speaker as Linkin Park,
underneath it. The robot woke, answered, and was drowned out.

## Evidence

A 35 s six-channel capture was taken while the music played and the phrase was
shouted five times, then measured per 250 ms frame.

**The voice reached the processed channel without difficulty:**

```
  t(s)        ch0     rawmic   ch0/raw dB
  1.75        2.6       55.6        -26.6     <- music only, cancelled
  2.25     1884.4      296.2         16.1     <- shout
  4.25     3269.9      353.8         19.3     <- shout
  8.75     1949.1      188.2         20.3     <- shout
```

ch0 sits at ~3 while music plays alone and jumps past 3000 on speech — better than
50 dB of separation. Near-end speech is not being suppressed.

**The detector decoded it, replayed offline through its own `--replay`:**

```
HIT conf=1.00  call  گردو بابا یه
HIT conf=0.87  call  گردو بابا
HIT conf=1.00  call  گردو بابا
HIT conf=1.00  call  گردو بابا
4 hit(s) at threshold 0.6
```

Four of five shouts, all high confidence, on the exact audio captured during
playback. Hardware and decoder both cleared.

## Wrong turns

**1. Blamed gain staging.** `AUDIO_MGR_MIC_GAIN 10.0` against `AUDIO_MGR_REF_GAIN
1.9` looked like a 5:1 imbalance that would drive the mic path into distortion the
linear AEC could not cancel. Measured and false: raw mic peaks reached 850 of
32768, **2.6% of full scale**. Nothing was near clipping. The imbalance is harmless.

**2. Blamed double-talk suppression.** `PP_DTSENSITIVE` is the documented tradeoff
between echo suppression and double-talk, and 12 looked worth raising. The capture
shows near-end speech passing at +16 to +20 dB relative to the raw mics. There is
no gating to fix. **Left at 12.**

**3. Measured echo with nobody speaking, then reasoned about a case it did not
cover.** An ERLE of 38.5 dB on ch0 proves the robot does not hear *itself*. It says
nothing about whether it can hear *someone else* while playing — which was the
actual question. Two different measurements; only one was taken.

## The one real hardware finding

**The control interface had never been reachable.** `~/reSpeaker_XVF3800_USB_4MIC_ARRAY`
is a different product's repo: its tools default to USB **PID 0x001A**, and this
board is a reSpeaker **Flex**, **0x001E**. The compiled `xvf_host` has it baked in
and can never connect.

```
$ ./xvf_host --use usb VERSION
Device (USB)::device_init() -- No device found

$ python3 xvf_host.py --pid 0x001E VERSION
VERSION: [1, 0, 0]      Done!
```

Log 018's follow-up — *"if echo leaks: tune with `xvf_host`"* — was never actionable.
**Every AEC parameter on this board is still factory default**, and measured fine:
`SHF_BYPASS 0`, `AEC_AECCONVERGED 1`, ERLE 38.5 dB on ch0.

Permissions were never the problem. The udev rule works; the node is
`crw-rw----+ root plugdev` and `jarvis` is in `plugdev`.

## Also measured: never use ch1

| channel | ERLE |
|---|---|
| ch0 (conference, in use) | **38.5 dB** |
| ch1 (ASR beam) | **3.9 dB** |

Log 018 left a follow-up suggesting ch1 for the wake word if ch0's noise suppression
hurt Vosk. It would hand the detector the robot's own voice almost uncancelled.
**Struck.**

## Fix

Pause a playing video for the duration of a call, resume it afterwards.
`video_snapshot()` and `video_action()` added to `wake_word.py`; the pause happens
**before** the chime so the chime is audible too, and the resume sits in a `finally`
so no exit path — refused session, already-active session, exception — can strand a
paused video.

Only a video *this code* paused is resumed. One the owner had already paused stays
paused, which is why `video_snapshot()` returns both flags rather than just
`playing`.

## Verification

```
snapshot before : (True, False)
pause accepted  : True
snapshot paused : (True, True)
resume accepted : True
snapshot after  : (True, False)
```

Exercised against a real playing video on the robot. Position preserved across the
cycle. `wake-word.service` restarted and `active`; test suite 9 passed.

**Not verified:** barge-in — interrupting the agent mid-sentence while it speaks.
That needs a person at the robot during a live call, and is the one case still
without a measurement.

## Separately fixed

The udev rule installed on the Jetson was the **one-stanza** version: 1022 bytes
against the repo's 1874. The re-enumeration repair hook from log 022 was committed
but never deployed, so only the 30 s timer was catching a dropped board. Installed,
and confirmed to match:

```
$ udevadm test --action=add /sys/.../1-2.3
SYSTEMD_USER_WANTS=gerdoo-audio-repair.service
```

## Takeaways

- **Read the log before measuring the hardware.** `triggers.log` held the answer in
  three lines and was consulted after three hours of audio analysis. The cheapest
  instrument in the system is the one already recording.
- **A component that goes deliberately deaf must say so where the owner can hear
  it.** "Detector paused" was printed to a journal nobody was reading, while the
  robot sat there looking like it had ignored ten shouts.
- **An action that seizes the speaker must first quiet whatever else owns it.**
  The `stop` phrase had this right; `call` never did.
- **Check the product ID before trusting a vendor tool's silence.** "No device
  found" meant the wrong product's repo, not a permissions problem, and it
  invalidated a follow-up that had been sitting open since log 018.
