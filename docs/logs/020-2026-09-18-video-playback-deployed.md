# 020 — Video playback deployed, and six wrong theories about a deaf microphone

| | |
|---|---|
| **Date** | 2026-09-18 |
| **Type** | Deployment + debugging |
| **Status** | ✅ Playback working · ⏳ Wake word during loud playback unresolved |
| **Severity** | Routine, with one unresolved fault |

---

## What went live

The video playback work from log 019 reached the robot and works: a YouTube URL
or a search phrase, sent from the control panel or spoken to the voice agent,
plays fullscreen over the kiosk face.

| Step | Result |
|---|---|
| `mpv` 0.34.1, `socat`, `yt-dlp` 2026.08.19 installed | apt for the first two, **pip for yt-dlp** — apt's is from 2022 and fails against today's YouTube |
| `deploy.sh` | robot-face synced, `video-player.service` enabled and active |
| Wake word | `wake_word.py` **and** `phrases.py` copied together, service restarted |
| Shared token | minted into the robot's gitignored `config.json` and `voice-agent/.env` |
| Token verified from off-box | no token → 403, correct token → 200, wrong token → 403 |
| First playback | search phrase → title resolved → fullscreen on the robot's screen |

The bench check that log 019 listed as unverified — **does mpv's window actually
cover the kiosk face** — passed. It needed one fix: `--fullscreen` in the unit
did not stick, because the window is created lazily when a file loads. Setting
`fullscreen` per file from the Lua script is what actually covers the face.

## Decisions, and why

**`-I 1` on the yt-dlp search, timeout 25s → 40s.** A play request sat in
`thinking` and then failed with "yt-dlp timed out". Measured on the robot: the
same search took 4s once and then ran past two minutes twice — while having
already printed a usable result within seconds. `subprocess.run` waits for the
process to EXIT, so a search that had answered still timed out. `-I 1` processes
only the first result: 3-4s, consistently. `--flat-playlist` is faster still (2s)
but its top hit for a singer's name is the artist's **channel**, not a video, so
it cannot be used here.

**`_ensure_mic()` before a call.** `gerdoo_mic` — the remapped source carrying
the XVF3800's processed channel — vanished mid-session. PulseAudio drops a
remapped source when its master disappears for a moment, and nothing put it back,
because `audio-setup.sh` only runs when the wake-word service starts. With it
gone, the browser fell back to the raw six-channel input, which mixes the
un-cancelled microphones in, and the robot transcribed its own voice. The failure
is silent: every service reports healthy. `/api/voice/wake` now checks for the
source and re-runs the audio setup if it is missing, because a call is the one
moment it has to be right.

**Preemptive generation OFF.** The agent said it would play a song and never
called the tool: one second from `thinking` to `speaking`, no tool call in the
trace. livekit-agents enables preemptive generation by default, and passing a
`turn_handling` dict does **not** opt out — the library fills in every key you
omit from its own defaults. It answers from a PARTIAL transcript, before the turn
ends. A speculative reply is a bad trade for a robot that acts on what it hears.

**System prompt hardened.** She may not say she is playing something unless
`play_video` actually returned success. Saying it is not doing it.

**Model `gemini/gemini-3.5-flash-lite` → `gemini/gemini-3.8-flash`.** Tool calling
was measured against the proxy with the real system prompt and all four tools, on
three cases: "play me a song" must call `play_video`, "what time is it" must call
`what_time_is_it`, and plain chat must call nothing. Results are in
`voice-agent/.env.example`. Two traps worth knowing: anything beginning
`openrouter/` fails with "Missing Authentication header" unless an OpenRouter key
is configured on the proxy itself, and the id needs its provider prefix — bare
`gemini-3.8-flash` reports "no healthy deployments".

**Speaker 100% → 85% (−9 dB).** An echo experiment, not a considered setting. See
the unresolved fault below.

**Double-tap to seek.** `mpv-seek.lua`: double-tap one side of the screen to skip
forward ten seconds, the other side back. It lives inside mpv because mpv owns
the screen during playback — a handler in the kiosk page never sees the touch.
The panel is mounted rotated, and a touchscreen is not necessarily rotated in step
with the display, so the script reports the tap's coordinates on screen until the
axis is confirmed. **Not yet calibrated.**

**udev rule for the array's control interface.** `99-respeaker-xvf3800.rules`
makes `xvf_host` usable without root, which is the only way to read or change the
board's own DSP settings. The bundled compiled tool is built for the other
XVF3800 board and cannot see the Flex; the Python one takes `--pid 0x001e` and
works.

## The unresolved fault

**While music plays, the microphone effectively stops hearing the room.** You have
to walk up to the array and raise your voice for "گردو بابا" to register.

Six explanations were proposed and all six were killed by measurement:

| Theory | Killed by |
|---|---|
| The browser was on the raw, un-cancelled source | It was provably on `gerdoo_mic` during the bad call |
| A weak "lite" model ignoring tools | Same model called the tool 5 times out of 5 with the real prompt and all four tools |
| mpv's own `ytdl_hook` hanging on resolution | Resolved in 5s, three times out of three |
| Automatic gain control ducking the near end | `PP_AGCGAIN` pinned at its maximum of 32.0 in both conditions |
| Beam gating silencing inactive beams | `AEC_FIXEDBEAMSGATING` is 0 — gating is off |
| The beam selector starved of speech energy | The zeros were measured **against a paused player** — my own error |

The last one deserves emphasis: `AEC_SPENERGY_VALUES` read `0.000` on all four
beams, which looked decisive, and it was an artefact of mpv having been left
paused by an earlier test. With music genuinely audible the same reading is in the
hundreds of thousands.

**What is actually known:** the hardware echo cancellation works — with playback
verified and no clipping, the processed channel measured *quieter* with music
playing than paused. The board detects plenty of speech energy during playback.
And the symptom is real and reproducible for the person in the room.

**Next test, which needs a person and a quiet room:** the wake word at 50% speaker
versus 100%, same phrase, same distance, reading the confidences out of
`triggers.log` afterwards. If it triggers reliably at 50% and not at 100%, the
answer is a volume ceiling during playback.

## Wrong turns worth recording

- **Three measurements in a row were confounded by unverified preconditions.**
  Twice the player had been left paused by an earlier test and the "music playing"
  half was captured against silence; once the clip ended mid-sweep. Every
  conclusion drawn from them was wrong. The fix was a harness that verifies
  playback immediately before and after each capture and refuses to report a
  sample it cannot vouch for.
- **Even that harness could not settle it**, because the room itself was not
  controlled — a silent speaker measured 30× the residual of a loud one, which is
  someone moving or speaking near the array, not an echo measurement.
- **Comparing a gain-controlled channel against raw ones measures the gain
  control, not the canceller.** Channel 0 carries AGC; its absolute level says
  nothing about how much echo was removed.
- **Deleting the plan's scratch workspace deleted the Flask virtualenv with it**,
  so the twenty route tests silently SKIPPED rather than ran. A suite that reports
  "77 passed, 1 skipped" while an entire file is missing looks healthy.
- **`ambient.wav` is truncated every time the wake-word service restarts**, because
  the recorder opens it for writing. The rolling recording used for regression
  checks only ever covers the period since the last restart.

## Security and safety review before publishing

This repository is public. Checked before committing:

- **No secrets are tracked.** `voice-agent/.env` (API keys and the shared token),
  `robot-face/config.json` (the token, the panel password hash, the Flask secret)
  and `robot-face/deploy/deploy.env` (the robot's address) are all gitignored, and
  that was verified with `git check-ignore` rather than assumed.
- **The token was never printed.** It was generated, written into both files and
  verified by comparing SHA-256 fingerprints; the value itself never entered a
  terminal, a log, or a commit.
- **No hostnames, addresses, usernames or personal names** in any committed file.
  `<robot>` is the placeholder convention; a stale `robot.local` in
  `.env.example` was replaced.
- **The udev rule is scoped to one device** — vendor `2886`, product `001e` — and
  grants access to the seat user and the `plugdev` group, not to everyone. It
  changes nothing about the audio path; it exists only for the DSP control
  interface.
- **`.env.example` carries names with empty values**, never real ones.

## Takeaways

- **Verify the precondition, not just the result.** Three measurements today were
  destroyed by a paused player nobody checked for. A measurement harness that
  cannot vouch for its own conditions produces confident nonsense.
- **A default you did not set is still a decision.** Preemptive generation was on
  because the library defaults it on, and passing a partial config dict silently
  accepted every other default with it.
- **When a tool answers early and exits late, waiting for exit is the bug.**
- **A silent fallback is worse than a failure.** The missing `gerdoo_mic` degraded
  audio quality with every service still reporting healthy.
