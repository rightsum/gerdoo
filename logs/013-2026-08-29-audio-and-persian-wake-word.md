# 013 — Audio output, and a Persian wake word

| | |
|---|---|
| **Date** | 2026-08-29 |
| **Type** | Feature bring-up — audio + speech |
| **Status** | 🔄 Working, being tuned — false positives in real use, range ~4 m |
| **Severity** | Routine |

---

## Goal

Get sound out of the robot, then have it listen for the Persian phrase
**"Gerdoo, baba"** (گردو بابا) and respond with a sound. The trigger only — what it
*does* on hearing the phrase comes later.

## Audio output

The NBFINE USB speaker enumerates as **card 3**, `USB2.0 Device`, at
`usb-3610000.usb-2.1.3`. Stereo out at 48 kHz S16_LE, plus a mono capture endpoint —
it has a mic of its own.

**It was not broken, it was turned down.** The ALSA hardware mixer `PCM` sat at
**39/255 (15%)**, which is what made everything sound faint. PulseAudio's level rides
on top of that, so the hardware mixer is the one that matters:

```sh
amixer -c 3 sset PCM 80%          # the control that actually matters
pactl set-default-sink alsa_output.usb-Generic_USB2.0_Device_20170726905923-00.iec958-stereo
```

Set as the default sink, so anything the robot plays goes there without a device flag.

> The sink defaults to the **iec958** (S/PDIF) profile. If PulseAudio playback is ever
> silent while direct ALSA works, switching the card to `analog-stereo` is the fix.

## Wake word — what worked

**Vosk offline ASR, Persian small model, with the decoder's grammar restricted to the
wake phrase and nothing else.** Runs on CPU, fully offline, no audio leaves the robot.

| | |
|---|---|
| Model | `vosk-model-small-fa-0.42`, 97 MB, in `~/models/` |
| Mic | Brio 500 — chosen over the speaker's own mic so the robot cannot hear itself |
| Service | `wake-word.service`, systemd `--user`, enabled at boot |
| Bench result | 18/18 detections over **one minute** of speech — see the correction below, this did **not** hold in service |

## Wake word — the wrong turn, and why it was wrong

The first live test detected roughly **70%** and fired on unrelated speech. Two mistakes,
both mine, both worth remembering:

**1. Calibrating in open-transcription mode.** Free-form decoding lets "گردو" compete with
every acoustically similar Persian word. The log shows the model settling on a bare
`بابا` again and again, producing `کردی` from ordinary speech, and writing the full
`گردو بابا` correctly only **once**.

**2. Firing on partial hypotheses.** Partials are unstable mid-utterance. One trigger
fired in the middle of *"الان حالم خوبه…"*, a sentence that does not contain the phrase.

Restricting the grammar to `["گردو بابا", "[unk]"]` fixed both. The decoder can now only
emit the phrase or "unknown", so there is nothing for it to drift toward. Firing moved to
final results only.

> Deliberately **not** in the grammar: `بابا` on its own. Calibration showed the model
> emitting it constantly from ordinary speech, so including it invites false accepts.

## Tuning by replay, not by asking

The detector can record its session (`--record`) and replay it (`--replay`), so parameters
are swept offline against real audio instead of asking a human to repeat a phrase for
every value. Two sweeps ran against one 100 s recording:

**Threshold — irrelevant.** 18 hits at every threshold from 0.0 to 0.8, 17 at 0.9. The
confidences are bimodal: a true utterance scores ~1.0, a miss produces no match at all.
**The grammar is the discriminator, not the confidence gate.** Threshold is kept at 0.5
as insurance for noisier conditions, not because it is doing work today.

**Gain — real, and measurable.** This is what recovered the far-field misses:

| Gain | Hits |
|---|---|
| 1.0× | 18 |
| 2.0× | 19 |
| 2.5× | 20 |
| **3.0×** | **21** |
| 3.5× | 21 |
| 4.0× | 20 |
| 6.0× | 17 |
| 12.0× | 15 |

3.0× it is. Above ~3.5× clipping and amplified noise take back what gain gave. The three
recovered hits are the low-confidence tail (0.73, 0.82, 0.84) — exactly the far-field
attempts.

Hardware gain was tried first and is nearly exhausted: the Brio's ALSA capture went
50 → **54 dB** (72/72) and its Pulse source 86 → 100%, worth only ~3.4 dB of ambient.

## Gotchas, all of which cost time

- **`paplay` accepts an mp3 path and plays nothing.** No error. Indistinguishable from the
  detector not firing. `play()` now dispatches by extension — `mpg123` for compressed,
  `paplay`/`aplay` for PCM — and complains if no player exists.
- **PortAudio device indices move** between reboots and replugs, exactly like
  `/dev/ttyACM*`. The service selects the mic by **name** (`--device-name Brio`).
- **Mic gain does not survive a reboot.** Since the 4 m range depends on it, the unit
  re-applies it in `ExecStartPre`.
- **The USB speaker's mic is 48 kHz-only** and PortAudio refuses to open it at 16 kHz.
  The pipeline captures at 48 kHz and decimates by exactly 3 — a clean integer ratio,
  and it keeps one code path for both mics.
- **`python3-venv` is not installed** and needs a sudo password. Installed with
  `pip3 install --user` instead. Worth fixing properly at some point.

## Verification, and where it was not good enough

Bench, 2026-08-29:

- 18/18 utterances detected, all decoded as `گردو بابا`, confidences 0.73–1.00
- No false triggers across **~1 minute** of unrelated Persian conversation
- Service survives restart, enabled at boot

**That minute was written up as "zero false triggers". It should not have been.**
A single minute cannot support that claim, and real use disproved it within a day.

## Correction, 2026-08-30 — false positives in service

Reported: with people talking nearby, it fires on wrong words repeatedly.

### Nothing had been recorded

The first thing asked for was the trigger log. There wasn't one.
**systemd `--user` journald is not persisted on this box** — `journalctl --user -u
wake-word` returns "No journal files were found", and the same is true of
`micro-ros-agent`. The service had run for a day with its stdout going nowhere.

The logging was never verified when the service was installed. Diagnostics that have
not been read once are not diagnostics.

Now fixed: `--log` appends every trigger to a file, and `--save-hits` writes **3 seconds
of the audio that caused it** — the run-up, not just the tail, so a false positive can
actually be listened to.

### Root cause: the grammar was too narrow

`["گردو بابا", "[unk]"]` gives the decoder essentially one real option. Vosk's `[unk]`
is a weak absorber, so ordinary speech has nowhere to go **but** the wake phrase.

This is the opposite of the intuition that led to it. Tightening a keyword grammar feels
like it should reduce false accepts; past a point it does the reverse, because false
accepts need somewhere else to land.

### Fix: a filler grammar, plus requiring both words

`FILLER_WORDS` adds competition — the near neighbours of `گردو` that the open-mode
calibration transcript actually produced (`کردی`, `کردم`, `کرده`), bare `بابا`, and
common conversational Persian.

`score()` now requires **both** `گردو` and `بابا`. Matching on the head word alone was
safe under the strict grammar but is not under filler, where `بابا` can be emitted
on its own.

### Measured cost, on the existing recording

| Grammar | Hits on `session1.wav` |
|---|---|
| `strict` | 21 |
| `filler` | **17** |
| `open` | 1 |

Filler costs ~19% recall. **What it buys in precision is not yet measured** — there is
no recording of people talking without the phrase, which is exactly the data that was
missing all along.

Collection is now running: the service records continuously to `ambient.wav`, so
false-positive rate per minute can be counted per grammar offline instead of guessed.

### If filler is not enough

Two-stage: filler grammar as a cheap first pass, then re-decode the buffered 3 s with
the **open** model and require the phrase to survive both. Roughly doubles cost per
candidate, but only runs on candidates. Not stacked on yet — measure first.

## Takeaway

**Verify the diagnostics before trusting the system.** A day of running produced no
evidence because nothing checked that the log worked.

**A narrower grammar is not a safer grammar.** False accepts have to land somewhere; if
the only thing on offer is the wake phrase, that is where they land.

**One minute is not a false-positive test.** Precision needs long, boring, real audio —
and it needs to be recorded, or the tuning is guesswork.

## Open

- **False-positive rate is unmeasured.** `ambient.wav` is collecting now; replay it
  across `strict` / `filler` / two-stage and count false accepts per minute.
- **Recall cost of `filler` needs confirming live** — 17 vs 21 on a recording is not the
  same as 17 vs 21 spoken across a room.
- **Range caps at ~4 m.** The Brio is a webcam mic built for someone sitting in front of
  it. Software gain recovered some of it, but gain cannot improve signal-to-noise — past
  4 m this needs different hardware, not more tuning. A USB conference mic would change it.
- **The trigger only plays a sound.** Hooking it to actions is a change in `play()` /
  the trigger branch.
- The response sound is `sounds/janam.mp3`; `bing.wav` is kept as a fallback.

## Aside — LocateAnything is installed and has never been run

Found while looking for models: `~/models/locateanything/` holds
`LocateAnything-3B-Q4_K_M.gguf` (2.0 GB) and `mmproj-LocateAnything-3B-BF16.gguf`
(833 MB), installed 6 Aug. The runtime is a full CUDA build — `~/src/llama.cpp-la`,
branch `mtmd-grounders`, with `llama-mtmd-cli` and `libggml-cuda.so` built for
`CMAKE_CUDA_ARCHITECTURES=87` (correct sm_87 for Orin).

Nothing in shell history suggests it has ever been run, and no benchmark exists. That is
exactly the gap `ACTION-PLAN.md` G6 check 3 flags: the ~1–2 s/query figure there is
**scaled from an H100, not measured**. One timed query on real hardware would close it.
