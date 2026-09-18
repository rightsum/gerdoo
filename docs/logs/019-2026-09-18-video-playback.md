# 019 — YouTube video playback on the kiosk screen

| | |
|---|---|
| **Date** | 2026-09-18 (opened and code-complete same day; still open — see Status) |
| **Type** | New feature |
| **Status** | 🔄 Code complete, reviewed, 10/10 plan tasks merged to branch `video-playback` · ⏳ Not yet deployed to the robot or exercised against a real player, a real call, or a real wake-word session |
| **Severity** | Routine feature work, but ships a deployment trap worth reading before the next `wake-word` deploy (see below) |

---

## Why

Ask for a video, out loud or from the control panel, and it plays fullscreen
on the robot's screen — over the kiosk face, which returns when the video
stops. A voice call takes priority: if one starts while a video is playing,
the video stops and resumes near where it left off once the call ends; if a
video is requested *during* a call, it starts the moment the call ends.

## Approach: mpv + yt-dlp, not the two alternatives considered

`mpv` plus `yt-dlp`, in a window over the kiosk, controlled through mpv's
JSON IPC socket. Two alternatives were rejected at design time
(`docs/superpowers/specs/2026-09-18-video-playback-design.md`):

- **Video inside the kiosk page** (`<video>` fed by a `yt-dlp`-resolved
  URL). YouTube's usable formats are DASH, which needs an MSE player in the
  page; stream URLs are signed, throttled and expire. The single-file
  format that a plain `<video src>` could use tops out at 360p and is being
  retired. Looks simpler on paper, fails in ways that are painful to debug
  on a screen with no console.
- **FreeTube with `xdotool` keystrokes.** No API and no way to read what is
  playing, so neither the control panel nor the voice agent could show or
  confirm state — every "is it playing, and what" question would be a
  guess.

`mpv` was chosen because `yt-dlp` — bundled through mpv's `ytdl_hook` —
absorbs YouTube's signature and throttling changes on its own release
cadence, and because mpv's socket reports position, title and paused state,
so the panel shows what is *true* rather than what was last requested.

## What was built

Ten tasks, executed and reviewed one at a time against a written plan
(`docs/superpowers/plans/2026-09-18-video-playback.md`), each with its own
commit:

1. `robot-face/video.py` — parsing a start time out of what people actually
   paste (`90`, `1:30`, `1:02:03`, `1h2m3s`, or a `t=` already in the URL),
   plus the pure logic around the player.
2. The mpv JSON IPC client — one UNIX socket, one command per connection.
3. `resolve()` — a URL is kept as given (title fetched separately); a
   search phrase goes through `yt-dlp "ytsearch1:..."`. Runs as an argv
   list, never `shell=True`, and the search branch always prefixes
   `ytsearch1:` so typed or spoken text can never pose as a leading `-`
   flag to yt-dlp.
4. `video-player.service` — one long-lived `mpv --idle`, plus the repo-side
   half of the deploy script. (The robot-side install — `apt-get install
   mpv socat`, needs a password this project's automation does not have —
   was always going to be a manual step; see **Not verified** below.)
5. `/api/video/play|stop|pause|resume|status` in `robot-face/app.py`, a
   shared-token guard (`hmac.compare_digest`, not `==` — closes a timing
   side-channel on the system's only shared secret), and the deferral rule
   for when a call is live.
6. The other half of that rule: `_video_yield_to_call()` /
   `_video_resume_after_call()`, wired into `_set_voice()`'s idle↔non-idle
   transitions.
7. The Video card on the control panel — play/pause/resume/stop, a start
   field, the currently-playing title, live status polling.
8. `wake_word.py` learns a second tail on the existing wake grammar: "گردو
   بسه" (and "گردو استاپ") stops a video. Split the matching logic into a
   new `phrases.py` so it can be unit-tested without the audio stack.
9. `voice-agent/video_control.py` and two new agent tools, `play_video` /
   `stop_video`, so asking Gerdoo to play something mid-call ends the call
   and starts the video.
10. This entry, plus the reference-doc updates in `inventory.md` and
    `README.md`.

## Behaviour: how the screen is shared with a call

- **A call takes the screen.** The moment voice state leaves `idle`, any
  playing video is stopped (not paused — pausing would leave mpv's window
  up, covering the face behind a frozen frame) and its URL, title and
  position are written to one pending record. The window goes away and the
  face is visible again for the call.
- **The call ends, the video resumes** near where it left off, read back
  from that same record.
- **A video asked for *during* a call** — from the panel, or "play me X"
  spoken to the agent — writes to the exact same record instead of calling
  `play_url` immediately, and starts the moment the call's `idle`
  transition fires the resume path.
- **Both paths share ONE pending record**, not two, specifically so an
  interrupted video and a video requested mid-call cannot both be live and
  race each other for the screen when the call ends. Confirmed in review by
  tracing the transition table by hand: yield fires only on idle→non-idle,
  resume only on non-idle→idle, no double-fire, no idle→idle trigger.
- **If the resume itself fails** (player unreachable, video gone), the
  record is cleared anyway rather than retried — a stuck record would tell
  the panel a video is coming that never will. The trade-off: a transient
  player restart loses the user's place instead of quietly healing, but
  recovery is one click (Play) or one sentence away, and that beats state
  that lies about what is about to happen.

## The deployment trap — read this before touching wake-word

`wake_word.py` now does `import phrases` at module scope (the matching
logic — grammar, scoring, the head/tail phrase table — moved into
`wake-word/phrases.py` so it can be tested on a machine with no numpy,
scipy or Vosk installed). That means **`wake_word.py` and `phrases.py` must
reach the robot together, every time.** Copy one without the other and the
wake-word service fails to import at startup — the robot stops answering to
its own name, silently, until someone notices and reads the journal.

The systemd unit runs `wake_word.py` by absolute path with no
`WorkingDirectory` override, and Python puts the *script's own* directory on
`sys.path` regardless of cwd, so `import phrases` resolves correctly as
long as both files live in `~/wake-word/` on the robot. The only failure
mode is a partial copy.

## `yt-dlp`: from pip, not apt

Ubuntu's apt candidate for `yt-dlp` is a 2022 build and fails against
today's YouTube — signing and throttling changes move faster than the
distro package. Install and update it with:

```bash
pip3 install --user --upgrade yt-dlp
```

`video-player.service` points mpv at that pip copy explicitly
(`--script-opts=ytdl_hook-ytdl_path=%h/.local/bin/yt-dlp`), so an apt-only
`yt-dlp` on the PATH is never picked up by accident. This is the piece most
likely to rot silently: nothing about a stale `yt-dlp` shows up until a
video simply refuses to resolve, months from now, with no error that says
why.

## The 16 kHz ceiling

The robot's only playback device is the XVF3800 (log 018), locked to 16 kHz
S16_LE on both capture and playback. Speech in a video is fine at that rate;
music will sound the way it does over a phone call. Nothing in this plan
works around that — it is a hardware property of the only speaker the robot
has, and raising it would mean a second audio path outside the array's echo
cancellation, which is exactly the multi-clock problem log 018 removed.

## The token setup

A shared secret authenticates the voice agent (running on a different
machine) to the robot's Flask app: `video_token` in the robot's gitignored
`robot-face/config.json`, matched by `VIDEO_BASE_URL` / `VIDEO_API_TOKEN` in
the gitignored `voice-agent/.env`. Minting the token itself was deliberately
left to the human running the robot — it is both a robot-side change and
security-sensitive, the same reason the `apt-get install` step was. **No
real token value or hostname is written in any committed file**; every
command in the plan and this entry uses `<robot>` for the host.

## Verification

Everything below is what actually ran, on a development machine, against
fakes — not on the robot:

- `cd robot-face && ../.superpowers/sdd/2026-09-18-video-playback/venv/bin/python -m pytest tests -q`
  → **95 passed** (Flask installed, a throwaway venv this plan's tasks
  needed since Flask is not on this machine outside it)
- `cd robot-face && python3 -m pytest tests -q` → **77 passed, 1 skipped**
  (the Flask-dependent video-route tests guard their import with
  `pytest.importorskip("flask")`, so a bare machine skips rather than
  errors at collection)
- `cd wake-word && python3 -m pytest tests -q` → **9 passed** (on a machine
  with no numpy/scipy/vosk installed — the proof that splitting the
  matching logic into `phrases.py` achieved what it was for)
- `cd voice-agent && python3 -m pytest tests -q` → **61 passed**

Every task's diff went through an independent review pass before merging;
five review rounds produced a fix (constant-time token comparison, a
deploy.sh block that could abort an unrelated deploy on a missing `mpv`, a
stuck pending record on a failed resume, a frozen "unreachable" panel card,
and a false comment about worker-process reuse). All are in the individual
commits on `video-playback`.

## Not verified — read before trusting this live

Nothing in this feature has been exercised against a real player, a real
call, or the robot's actual microphone. Specifically, none of the
following has been checked and all of it should be, in this order, before
relying on it:

- **That mpv's window actually covers the kiosk face fullscreen** on the
  real 5.5" panel. The unit file asks for `--fullscreen` and
  `--force-window=no`, and Task 4's review reasoned through the window
  manager interaction, but no one has watched it happen on the hardware.
- **That the wake word can hear "گردو بسه" over a video's own audio.** This
  is the one the XVF3800's hardware echo cancellation has to earn — the
  video plays through the same device the wake-word listens on. Log 018
  never tested this scenario (it tested a voice call, not a video), so this
  is genuinely new ground for the hardware AEC.
- **The hit-count replay check** (`wake_word.py --replay` /
  `--sweep-gain` against a saved recording) proving the two new stop
  phrases, "بسه" and "استاپ", do not fire on ordinary conversational
  speech the way the original "گردو بابا" grammar was tuned against. Design
  review reasoned about this from first principles (neither tail sits in
  the filler-word list that currently absorbs near-misses), but reasoning
  is not the same as running the recording.
- **End-to-end behaviour of the two agent tools, `play_video` and
  `stop_video`, against a live LiveKit session** — a spoken "play me X"
  mid-call, confirmed out loud, the call actually ending, and the video
  actually starting. `voice_control.py` is unit-tested against fakes only;
  nothing has spoken to a running agent.
- The panel walk-through itself: play-with-start-time landing at the right
  point, Pause/Resume/Stop returning the face on Stop, a search phrase
  resolving to the right video with its title shown, and
  `systemctl --user stop video-player` then pressing Play producing a
  clean "player unreachable" message rather than a hung page.
- The robot-side install steps this plan could never run non-interactively
  (`sudo` needs a password on this robot): `apt-get install mpv socat`,
  `pip3 install --user yt-dlp`, enabling `video-player`, minting
  `video_token` into `config.json`, and adding the matching values to
  `voice-agent/.env`.

## Deferred minors, carried from the review ledger rather than lost

- `parse_start` raises `ValueError` for a bad explicit start value but
  silently returns `None` for a malformed `t=` embedded in a URL — the
  asymmetry is real and undocumented in a comment (`video.py`).
- `_from_text`'s comment doesn't say *why* the clock-style regex is tried
  before the compact one (colon forms would otherwise fail the compact
  regex first).
- The mpv socket client's exception handling lists `FileNotFoundError` and
  `ConnectionRefusedError` alongside `OSError`, though the first two are
  already `OSError` subclasses — harmless, brief-mandated verbatim.
- The fake mpv server's serving thread in the test suite is never joined on
  teardown, only its listening socket closed. Daemon thread, no observed
  leak.
- `test_a_silent_player_raises_rather_than_hanging` exercises the EOF
  branch, not the `socket.timeout` branch — proves "raises rather than
  hangs" but leaves the timeout path itself untested.
- `_run`'s three internal branches in `video.py` (yt-dlp missing, timeout,
  non-zero exit) are never independently driven — every test monkeypatches
  `_run` wholesale, so a regression inside it would not be caught by this
  suite.
- `app.py`'s `st.get("position") or 0` maps an unknown position to the same
  0 as "at the start of the video" — unreachable in practice given
  `video.status()`'s contract, but worth a comment.
- Only `video.status()` raising is exercised for error tolerance around the
  resume path; `_current_url()` / `command()` failures share the same
  `try`/`except` by inspection but aren't independently tested.
- No test exercises `phrases.grammar()` / `phrases.strict_grammar()`
  directly — e.g. that all three wake phrases land in the JSON grammar sent
  to Vosk. Those two functions are exactly what changes false-accept
  exposure, which is why the ambient-recording replay check above matters.
- **The "گردو بسه" stop branch in `wake_word.py` runs before the panel's
  voice on/off master-switch check** (the check that normally keeps a
  disabled robot from acting on anything it hears). In practice the window
  is small — switching voice off releases the microphone within one poll
  interval — but it does contradict the stated rule that "off means the
  robot is not listening." Left as-is pending a decision on whether to gate
  the stop action on the switch too.
- `ctx.shutdown()`'s idempotence if the agent's own closing phrase and a
  video request land in the same instant is unconfirmed from source. The
  window is tiny and the worst case is a traced exception during teardown
  of a call that was ending anyway.
- No automated coverage of `agent.py`'s wiring itself (the tool bodies,
  `end_call`, `_watch_end_call`) — only `video_control.py`'s HTTP client is
  unit-tested. Matches the plan's stated scope for that task.

## Wrong turns and corrections along the way

- The plan's own dispatch brief for Task 10 pointed at a deploy.sh anchor
  ("wherever `face-track.service` is copied and enabled") that no longer
  existed — `gesture.service` was deleted when gesture detection was
  replaced by face tracking (log 017), and `deploy.sh` had been silently
  copying a file that was not there ever since, without aborting, because
  its remote check always exits 0. Caught during Task 4's pre-check and
  repaired in the same commit that added `video-player.service`, since it
  was the same section of the same file and the panel was actively
  pointing users at the stale instructions.
- Task 4's first cut enabled `video-player` with a hard `systemctl --user
  is-active` check at the end of its remote deploy chain — on a robot
  where `mpv` isn't installed yet, that check fails and aborts `deploy.sh`
  before the kiosk-autostart step, so any unrelated deploy would silently
  half-finish. Review caught it; the fix made that one check fail-soft,
  matching the pattern the lidar and face-track blocks already use for
  binaries installed by hand.
- Task 9's brief-supplied test for a connection failure never set
  `video_control.BASE_URL`/`TOKEN`, so it exercised the "not configured"
  branch instead of the one it meant to test. Caught in the plan's
  pre-flight self-review before the implementer even started, and fixed by
  monkeypatching both before the call, matching the pattern the
  neighbouring tests already used.
- Flask is not installed on the development machine the plan ran on, so a
  throwaway venv was created for it (git-ignored,
  `.superpowers/sdd/2026-09-18-video-playback/venv/`) — and the
  Flask-dependent route tests guard their own import with
  `pytest.importorskip("flask")` so the documented bare command still
  passes (skipping, not erroring) on a machine without it.
- The Flask test client always reports `REMOTE_ADDR=127.0.0.1`, which made
  the token-auth tests pass for the wrong reason (the localhost bypass, not
  the token check) until the fixture was changed to stop pretending to be
  local — otherwise the plan's security-relevant task would have shipped
  with its main code path untested.

## Takeaways

- **A pending-state record that both halves of a two-way transition write
  to is worth the extra indirection.** Writing "interrupted by a call" and
  "requested during a call" to two separate slots would have needed
  explicit conflict handling between them; one slot made the conflict
  impossible instead of merely handled.
- **State that lies is worse than state that is merely unhelpful.** Two
  separate reviews independently reached this same ruling — a frozen panel
  card showing a stale title next to the word "unreachable," and a pending
  video record that survives a failed resume forever — and both were fixed
  the same way: clear or repaint immediately, even if the underlying
  problem (a dead player, a lost position) is not itself fixed.
- **A module-scope `import` is a deployment dependency, not just a code
  dependency.** Splitting `wake_word.py`'s matching logic into `phrases.py`
  was the right call for testability, but it also means two files now have
  to move together to every target, forever — worth stating loudly in the
  log that a future "quick fix, just copy the one file" deploy will break.
