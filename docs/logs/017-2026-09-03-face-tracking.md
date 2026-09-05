# 017 — The neck follows your face

| | |
|---|---|
| **Date** | 2026-09-03 |
| **Type** | Feature — replaces gesture detection |
| **Status** | ✅ Working |
| **Severity** | Routine |

---

## What changed

Say the wake word and the robot turns to look at you, following your face for the
length of the call and re-centring afterwards. Hand-gesture detection is gone.

| | Was | Now |
|---|---|---|
| Detector | MediaPipe gesture recogniser, 8.4 MB | BlazeFace short-range, 225 KB |
| Tracking runs in | **The control panel's JavaScript** | A systemd service |
| Camera | Started by hand from the panel | Started with the call, stopped after |
| Trigger | Making a fist | The wake word |

## The tracking was in the wrong process

The old fist tracking lived in `control.html`, so the neck only followed anything
while somebody happened to have the control panel open in a browser. The robot's
own screen shows the face, not the panel — so in normal use it did nothing.

It now runs server-side in `face_tracker.py`, which polls `/api/voice/status`,
starts the camera when a call begins, drives the servos directly, and stops the
camera and re-centres when the call ends.

Geometry is separated into `face_tracking.py` so it can be tested without a
camera, a robot, or MediaPipe: 17 tests covering the deadzone, step clamping,
servo limits, largest-face selection, axis inversion, and that repeated
corrections converge rather than oscillate.

Deliberate choices: **largest face, not first**, so it attends to whoever is in
front of it rather than someone crossing behind; a **6% deadzone**, because the
detector's box jitters a pixel or two per frame and without it the neck hunts
continuously; a **6° step cap**, because the servos are driving a screen and one
SG90 has already been lost to abuse; and **hold position when the face is lost**
rather than hunting for it.

## Three definitions of "centre", all different

Asked to make 110/110 the default, the value turned out to be defined in three
places that disagreed:

| | Was |
|---|---|
| Tracker | 105/90, computed from the midpoints of the servo range |
| Panel centre button | 110/90 |
| Firmware boot position | 90/90 |

All three now say **110/110**, with a comment recording that this is a measured
property of the bracket, not the midpoint of anything — the gimbal is not mounted
symmetrically, so the middle of the servo travel is not the middle of the room.

## The servos were never commanded at boot

`setup()` attached them and set `lastPanWritten`/`lastTiltWritten` to the target,
but never actually wrote them. The loop only writes when the value changes:

```cpp
if (newPan != lastPanWritten) { servoPan.write(newPan); ... }
```

so the condition was never true and the servos held whatever position they
powered up in, while the firmware confidently reported the centre. The first
nudge then crossed the whole accumulated error at once.

This was invisible while the boot position was 90/90, because that happened to be
near where the servos naturally sat. Changing it to 110/110 exposed it.

The tilt inversion for the reversed mount now lives in a `writeTilt()` helper,
since it has to be applied identically at boot and in the loop, and two
hand-written copies of the same formula eventually disagree.

## "Smoothing" that peaked at 1200 deg/s

The easing looked gentle — 3% of the remaining distance per iteration — until you
notice the loop runs at ~999 Hz. Three percent of the remaining distance, a
thousand times a second, is a peak of about **1200 deg/s**. A human neck manages
100–200. It snapped to position and sounded mechanical doing it.

Now time-based and speed-limited: a 70 deg/s cap with an exponential ease over the
last few degrees, updated at **50 Hz** because that is the rate an SG90 actually
samples its input. Writing faster is churn the servo cannot see.

A settled SG90 also buzzes while holding position, so **pan detaches after 1.5 s
of stillness**. Tilt stays energised deliberately — it holds the screen's weight
and would drop if released.

## Two bugs where the display and the action disagreed

**The panel's centre button** displayed `110/110` and posted `tilt: 90`. An
earlier edit had updated the two variables and the label but missed the request
body. There were four copies of "the centre" in one short function; three were
changed. It is now a single `CENTRE_PAN`/`CENTRE_TILT` constant used by all of
them.

**`/api/servo` reported stale data.** It shelled out to `cat` on a serial console
shared with the 1 Hz heartbeat stream, then returned whichever line happened to
match. It reported `tilt=105`, `95` and `120` within six seconds while the real
target never moved — those were echoes of earlier commands still in the buffer.
It cost several rounds of chasing a fault that was not there.

**Fixed the same day.** Five faults in one short function: it never flushed, so
buffered output was read as the answer; it matched any line containing `SERVO`
and `set`, including old echoes; it held no lock, so concurrent requests
interleaved on one port; it hardcoded the board's serial number in the device
path; and it interpolated the command into a shell string.

`teensy.py` replaces it using stdlib `termios` — pyserial is not installed on
this board. It flushes input **before** writing, reads until a line actually
answers *this* command, holds a lock, and resolves the port by glob. **7 ms per
read, down from about 450 ms**, and identical across repeated and concurrent
reads.

> The first deploy returned `SERVO usage: SERVO pan=90 tilt=90  (0-180)`, because
> bare `SERVO` prints usage first and the position second — so the matcher took
> the help text and reported its example values as the position. There was a test
> for exactly that case, written against the string `"SERVO usage"` rather than
> the firmware's real output, so it passed while the bug was live. Same lesson as
> the tilt-direction test: a test written from an assumed output proves nothing.

## Tilt tracked the wrong way

With `tilt_inverted=False` the tracker chased away from the face until it hit
`TILT_MAX`, which is what "it goes down when I raise my head" and a servo target
pinned at exactly its clamp are describing from two sides.

The firmware already flips the tilt pulse for the reversed mount, and the tracker
sits on top of that, so a second inversion is needed. That is a fact about how
this gimbal is built rather than something derivable.

The test that covered this asserted the wrong convention, so it passed while the
robot misbehaved. It was rewritten to the measured behaviour in both directions,
noting that it was verified on the robot — a passing test proves nothing about
which way a servo turns.

## Other fixes

- **`sensor_guard()` blocked the tracker.** Starting the camera required a login
  session, which a background service does not have. Localhost now passes, the
  same latitude the wake-word service and frame endpoint already had.
- **The tracker logged nowhere.** `journalctl --user` is not persisted on this
  box, so a failure would leave no trace. It writes to `face-track.log` as well.
- **A bulk deletion broke the template.** Removing the gesture JavaScript took an
  `{% endif %}` with it, and the panel returned 500 for logged-in users. The
  check that missed it extracted the JavaScript and ran `node --check`, which
  strips Jinja tags first — so a broken Jinja block is precisely what it cannot
  see. Jinja block balance is now checked directly.

## Open

- **Pan direction is unverified** — only tilt was wrong in testing, but the same
  class of error applies.
- Camera start costs 1–2 s, so tracking begins slightly after the greeting.
  Keeping it warm was rejected on privacy grounds.
