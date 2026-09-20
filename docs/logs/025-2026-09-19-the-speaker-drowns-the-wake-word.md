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
**"Wake!"** control that starts a voice session directly, becoming **End** during
a call.

It settled into a wide, shallow, transparent **dome rising from the bottom
edge** — 740x185, with the ellipse centre *on* the screen edge, so the flat side
is the edge itself and every pixel of it is reachable. It took the colour of the
face rather than a colour of its own: read from the face element at paint time,
so it follows the robot through every voice state (cyan idle, amber connecting,
red on error) with no second table to keep in sync.

The container is click-through (`pointer-events: none`, with `auto` on the
buttons), so the face keeps the whole screen and taps that miss fall through.
Pause/resume and stop sit to the left, only while something is playing.

Two shape notes, both of which cost a round trip:

- **CSS needs the `/` radius form.** `border-radius: 370px 370px 0 0` is clamped
  by the 185px height and silently degrades into a rounded rectangle. The dome
  needs `370px 370px 0 0 / 185px 185px 0 0` — horizontal radii, then vertical.
- **The same shape in ASS** is two cubic beziers over the top (control points at
  0.5523r) closed with a straight line along the bottom, taking `rx` and `ry`
  separately so it can be wider than tall. Hit-testing is an ellipse test to
  match.

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

The first version was a small green circle floating above the bottom edge. It
was legible on a desktop screenshot and wrong on the robot: too small to hit,
and visibly a control bolted onto the face rather than part of it. Taking the
face's own colour and growing into the edge fixed both at once.

## The button broke calls before it fixed them

Minutes after deploying, every trigger failed with "can't connect". The server
was healthy the whole time — agent up, HTTP 200 from the robot in 11 ms, the
WebSocket endpoint correctly returning 401 without a token. The fault was the
new button.

```
22:54:30  connected; enabling mic
22:54:30  joinVoice FAILED: room is null
22:54:36  joinVoice FAILED: room.connect timed out after 15000ms   <- began 22:54:21
```

The second connect started *before* the first finished: **two `joinVoice()`
calls running concurrently over one shared `room`.** The button calls
`joinVoice()` directly, which POSTs `/api/voice/wake`, which sets the server to
`connecting`, which arrives over SSE, which makes `apply()` call `joinVoice()`
again. The existing `if (room) return` guard cannot catch it, because `room` is
only assigned *after* the token fetch resolves — both callers sail past it.

Fixed with a `joining` flag set before the fetch and cleared in a `finally`, plus
a condition on the failure path's `setTimeout(report('idle'), 5000)` so a stale
timer from a failed attempt cannot drag the *next* live call back to idle.

Verified: `join already in flight; ignoring` → `mic enabled` → `listening`, and
a second tap ends the call.

**The lesson is about adding a caller, not about the bug.** The wake word had
been the only thing that started a session, so a guard that assumed one caller
had held for months. The button did not change any of that code — it just became
the second caller, and that was enough.

## Getting the controls over the video: three designs, one survivor

The button is worthless on the face alone — the case it exists for is a playing
video, which is when shouting fails. mpv owns the screen then, so the kiosk
page's own toolbar is simply not visible.

**Design 1 — reserve a strip.** Size mpv to the screen minus the toolbar
(`--geometry=1920x890 --no-border --ontop`) and let the page show through below.
Blocked by the window manager:

```
mpv      _NET_WM_STATE_ABOVE
firefox  _NET_WM_STATE_FULLSCREEN
stacking bottom→top:  mpv, firefox
```

**xfwm4 stacks fullscreen above `_NET_WM_STATE_ABOVE`**, so the face covered the
video entirely. `--ontop` does not beat fullscreen, and `--kiosk` re-asserts
fullscreen after it is stripped.

**Design 2 — take the browser out of fullscreen.** `--kiosk` is what sets
`_NET_WM_STATE_FULLSCREEN`, so it was replaced with a `userChrome.css` that hid
the chrome and a launcher that declared the window
`_NET_WM_WINDOW_TYPE_SPLASH` — undecorated by definition and still in the WM's
normal layer, which is what let mpv float above it. `_MOTIF_WM_HINTS` was tried
first and is not reliable here: xfwm4 honoured it on some launches and drew
"Robot Face — Mozilla Firefox" across the top of the face on others.

It worked, and it was **backed out entirely**, for two reasons.

It cost **190px of picture** on a five-inch screen — the strip had to be that
tall because the Wake button has to be ~9mm to be hittable.

And it broke the screen. After a video stopped, the last frame stayed on the
display with the controls still painted on it — frozen. mpv's window was gone
and mpv was idle; the browser simply never repainted. There is no compositor
(`xfwm4 /general/use_compositing` is `false`), so X relies on Expose events, and
the SPLASH window did not act on them. `xrefresh` cleared the stale frame to
white and the face still did not come back. **A blank kiosk is worse than a
titlebar**, and design 3 does not need any of it: with the controls inside mpv,
the browser never has to leave fullscreen. `--kiosk` is back, unchanged from
where it started.

**Design 3 — draw the controls inside mpv. Shipped.** `mpv-seek.lua` renders an
ASS overlay: a translucent green "Wake!" circle bottom-centre, pause and stop
beside it, all at 50% fill alpha so the video reads through them. Taps are
hit-tested against the same coordinates they are drawn at, which sidesteps the
panel-rotation problem the seek code above has to deal with — seek needs to know
which side is *physically* left; a button does not.

mpv goes back to plain `--fullscreen`. The video keeps every pixel.

One bug worth recording: the first `draw()` almost always fails, because at
`file-loaded` the window has no size yet and `osd-dimensions` is 0. The redraw
that follows was gated on the overlay already existing, so it never came and
nothing was ever drawn. An `active` flag, set on `file-loaded` and cleared on
`end-file`, is what the observers key off now.

Verified end to end:

```
playing                      → video fullscreen 1920x1080, controls drawn over it
tap Wake (mpv overlay)       → voice=listening, video stopped, deferred=true
tap End (page's own FAB)     → voice=idle, video replayed, position advancing
```

## The video pause that was already there

Both this entry's button and log 024's change to `wake_word.py` added code to
quiet a playing video for the duration of a call. **Both were redundant and both
were reverted.**

`app.py` has done it for months, on every voice state change, whoever caused it:

```
before call: playing=true   deferred=false
during call: playing=false  deferred=true    <- _video_yield_to_call()
after call:  playing=true   position=12      <- _video_resume_after_call()
```

Measured with the toolbar and the detector entirely out of the picture, by
setting voice state directly. And the existing implementation is the better one —
it **stops** rather than pauses, because a paused mpv leaves its window on screen
with a frozen frame over the face. Log 024 has been corrected.

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
- **A workaround that survives testing can still be the wrong shape.** Taking
  the browser out of fullscreen passed every check put to it, then froze the
  screen on the one path nobody had exercised — stopping a video. It was only
  ever scaffolding for a strip that the final design does not need.
- **Grep for the behaviour, not for the file you are editing.** Two separate
  video-pause implementations were written and reverted in one evening because
  nobody looked for the one `app.py` already had, three functions from code that
  was being read closely.
- **Check the product ID before believing a vendor tool's silence.** "No device
  found" meant the wrong product's repo, and it had silently invalidated a
  follow-up open since log 018.
