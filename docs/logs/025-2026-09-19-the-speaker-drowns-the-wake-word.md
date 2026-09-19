# 025 — The speaker drowns the wake word, and no amount of DSP gets it back

| | |
|---|---|
| **Date** | 2026-09-19 |
| **Type** | Fault traced to physics + partial mitigation + one dead end |
| **Status** | ✅ Cause proven · 🔄 Touch fallback built, not usable during video · ❌ Wake word at volume unsolved |
| **Severity** | The robot cannot be woken by voice while it plays anything loud |

---

## Symptom

> "the music is playing i shouted gerdoo baba like 10 times but none detected"

and, decisively, later the same evening:

> "volume at 90% the wake didn't work, reduced to 10 and it worked"

## Root cause

**Acoustic masking at the microphone membrane.** At high playback the music
arrives at the array as loud as the speaker's voice, and the voice is gone before
any chip sees it. Nothing downstream can recover it.

The measurement that settles it — the **raw microphone**, with the AEC and the
suppressor bypassed completely:

```
90% volume, raw mic (no AEC, no post-processing):
  open-mode transcription : (nothing)
  wake-word detector      : 0 hits
```

Not degraded. Absent. Since the raw channel has no processing on it at all, no
firmware setting and no detector can be responsible.

Confirmed from the other direction by the owner: **mouth against the grille, same
music, same volume — it worked.** Perhaps 2 cm instead of 2 m, so 30-odd dB of
extra voice, and the identical system succeeds.

## The size of the gap

```
music at the raw mics       ~300 RMS
shout at normal distance    ~300-400 RMS
                            → 0-2 dB SNR

volume sweep, 10% -> 90%    13.5 dB at the mics
```

**13-15 dB is what has to be found**, without moving the speaker (25 cm from the
array, fixed) and without capping volume (both ruled out by the owner).

## Wrong turns

**1. Blamed gain staging, on a measurement taken at the wrong volume.**
`AUDIO_MGR_MIC_GAIN 10.0` against `AUDIO_MGR_REF_GAIN 1.9` looked like an
imbalance that would clip. It does not: peaks reached 850 of 32768, **2.6% of
full scale**. But the measurement that "disproved" it was taken with the sink at
**16%** — the case that already worked. Generalising from it was the real error,
and it cost the evening. *Measure at the operating point that fails.*

**2. Blamed double-talk suppression, then tested it.** `PP_DTSENSITIVE` is the
documented tradeoff between echo suppression and double-talk. Tried 12 (default)
and 10 at 90% with music plus a speech-band noise bed:

```
DTSENSITIVE=12 → 0 hits        DTSENSITIVE=10 → 0 hits
```

Open-mode transcription emitted **nothing** in either case, where at 16% it
happily transcribed Persian. Restored to 12. Not the problem.

**3. Oversold beamforming before reading the geometry.**

```
AEC_MIC_ARRAY_GEO: [0.022,-0.022,0] [0.022,0.022,0] [-0.022,0.022,0] [-0.022,-0.022,0]
```

A 44 mm square, 62 mm across the diagonal. Four omnidirectional microphones cap
out at `10*log10(4)` = **6 dB** of directivity however they are combined, and at
1 kHz the aperture is 0.18 wavelengths — far below the λ/2 needed for a real
null, so ~3 dB down there. Useful only above ~2 kHz, with spatial aliasing from
~3.9 kHz. **3-6 dB against a 13-15 dB gap.** Worth switching on, never the fix.
The speaker is in the far field at 25 cm (boundary ~2 cm), so a fixed beam would
at least behave predictably — but the ceiling is the ceiling.

## The one real hardware finding

**The board's control interface had never been reachable.**
`~/reSpeaker_XVF3800_USB_4MIC_ARRAY` is a different product's repo: its tools
default to USB **PID 0x001A**, and this board is a reSpeaker **Flex**, **0x001E**.

```
$ ./xvf_host --use usb VERSION          →  No device found
$ python3 xvf_host.py --pid 0x001E VERSION  →  VERSION: [1, 0, 0]  Done!
```

Log 018's follow-up — *"if echo leaks: tune with `xvf_host`"* — was never
actionable. Every AEC parameter is still factory default, and measures well:

| | |
|---|---|
| `SHF_BYPASS` | 0 (AEC on) |
| `AEC_AECCONVERGED` | 1 |
| ERLE, ch0 (in use) | **38.5 dB** |
| ERLE, ch1 (ASR beam) | **3.9 dB** |

**The hardware does its job.** It cancels the robot's own playback well. It
cannot undo masking, and no echo canceller can — cancellation is a ratio, so 38 dB
below a loud signal is still loud, and speaker distortion at high SPL is not in
the reference signal to be subtracted at all.

**ch1 is struck as a wake-word source.** Log 018 suggested it as an alternative
if ch0's noise suppression hurt Vosk; at 3.9 dB it would hand the detector the
robot's own voice.

## Mitigation built: a touch fallback

If shouting cannot work at volume, the screen can. Added to the kiosk face a
floating **"Wake!"** button — a circular FAB, centred at the bottom, which starts
a voice session directly. It becomes **End** during a call.

Transparent and click-through (`pointer-events: none` on the container, `auto` on
the buttons), so the face and any video keep the whole screen. Pause/resume and
stop appear beside it only while something is playing.

Three bugs worth recording, all of them things that look right in a desktop
browser and are wrong here:

- **Sizes were 2.75x too small.** The panel is 1920x1080 on a **5 inch**
  diagonal — about 440 PPI — and `devicePixelRatio` is 1, so CSS pixels are
  device pixels. A 76 px control is **4 mm** across and cannot be hit. Sized
  physically now: 156 px ≈ 9 mm, about an Android 48dp target.
- **`hidden` did nothing on the buttons.** `#toolbar button { display: inline-flex }`
  is an author rule and beats the UA stylesheet's `[hidden] { display: none }`.
  Media buttons stayed on screen with nothing playing.
- **Both play and pause icons drew at once.** `hidden` on an inline-SVG child
  does not hide it. One path whose `d` is swapped, instead of two overlaid SVGs.

## Dead end: the toolbar cannot be reached during video

The design was for the toolbar to stay visible while a video plays — the case
that matters most, since that is when shouting fails. It does not work, and the
reason is the window manager.

The video is native `mpv`, not in the browser. Sizing it to the screen minus a
64 px strip does work (`--geometry=1920x1016+0+0`, verified). But:

```
mpv      _NET_WM_STATE_ABOVE
firefox  _NET_WM_STATE_FULLSCREEN
stacking bottom→top:  mpv, firefox
```

**xfwm4 stacks the fullscreen kiosk browser above `_NET_WM_STATE_ABOVE`**, so the
face covered the video entirely. `--ontop` does not beat fullscreen, and
`--kiosk` re-asserts fullscreen after it is stripped. Reverted `mpv` to
`--fullscreen`; the comment in `video-player.service` records why.

Making it work requires **the browser to stop being fullscreen too** — dropping
`--kiosk` for an undecorated 1920x1080 window with chrome hidden via
`userChrome.css`. Not attempted: if it misbehaves, the robot boots to a broken
screen.

So today the Wake button helps on the face, not over music.

## Log 023 recurred, and the touch path is unverified because of it

At the end of the session the touchscreen was **absent from `lsusb` and from
`/proc/bus/input/devices`**, with X listing no pointer device:

```
$ xinput list
⎡ Virtual core pointer        id=2   [master pointer (3)]
⎜   ↳ Virtual core XTEST pointer  id=4  [slave pointer (2)]
```

Same branch as log 023: hub `1-2.1` now carries only `Port 5: Dev 9`, a
`USB Billboard Device` with no driver — a USB-C alt mode that failed to
negotiate. The controller log 023 recorded at `1-2.1.1` is gone. The display
still works; only touch is missing. Log 023's recovery was a full power cut of
the reSpeaker board, USB-C **and** the 12 V terminal.

**Consequence for this entry:** the Wake button was exercised through `xdotool`,
which drives XTEST inside the X server and bypasses the missing hardware. Its
logic is verified end to end — tap → `joinVoice` → "mic enabled" → `listening`.
**The actual finger path is not, and cannot be until the panel returns.**

## Takeaways

- **Measure at the operating point that fails.** An ERLE of 38.5 dB with nobody
  speaking, and a clean double-talk capture at 16% volume, were both true and
  both irrelevant to a fault that only appears at 90%.
- **Test the rawest signal early.** One replay of the uncancelled microphone
  would have ended the whole investigation in a minute: no speech there means no
  software anywhere can help, and every DSP theory dies at once.
- **Cancellation is a ratio, not a floor.** Any echo canceller's output scales
  with what it is cancelling. Buying one does not buy a quiet room.
- **A synthetic input is not a test of an input path.** XTEST proved the handler,
  and proved nothing about the touchscreen — which turned out not to exist.
- **Check the product ID before believing a vendor tool's silence.** "No device
  found" meant the wrong product's repo, and it had silently invalidated a
  follow-up open since log 018.
