# Video playback on the robot's screen — design

| | |
|---|---|
| **Date** | 2026-09-18 |
| **Status** | Approved, not implemented |
| **Supersedes** | nothing |

## Purpose

Send a YouTube video to the robot's screen — from the control panel or by asking
Gerdoo out loud — with an optional start position. It plays fullscreen over the
kiosk face. Say a short Persian phrase and it stops, the face comes back.

## Scope

**In:** one video at a time; URL or search phrase; start time; play, pause, stop
from the panel; play and stop from the agent; a direct voice phrase for stop;
automatic pause and resume around a voice call.

**Out (deliberately):** playlists and queues, a browsing UI on the robot, volume
control (the array's volume is already set), subtitles, playback history,
non-YouTube sources.

## Approach

`mpv` plus `yt-dlp`, in a window over the kiosk, controlled through mpv's JSON
IPC socket.

Two alternatives were rejected:

- **Video inside the kiosk page** (`<video>` fed by a `yt-dlp`-resolved URL).
  YouTube's usable formats are DASH, which needs an MSE player in the page;
  stream URLs are signed, throttled and expire. The single-file format tops out
  at 360p and is being retired. Looks simpler, fails in ways that are painful to
  debug on a screen with no console.
- **FreeTube with `xdotool` keystrokes.** No API and no way to read what is
  playing, so neither the panel nor the agent could show or confirm state.

mpv was chosen because `yt-dlp` — bundled through mpv's `ytdl_hook` — absorbs
YouTube's signature and throttling changes, and because the socket reports
position, title and paused state, so the panel shows what is true rather than
what was last requested.

## Components

### `video-player.service` (new, systemd `--user`)

One long-lived `mpv --idle` with an IPC socket. Idle means no window, so the
face is visible whenever nothing is playing. `loadfile` makes the window appear;
`stop` returns it to idle and the window goes away.

```
ExecStart=/usr/bin/mpv --idle=yes --force-window=no --fullscreen \
    --input-ipc-server=%t/gerdoo-mpv.sock \
    --script-opts=ytdl_hook-ytdl_path=%h/.local/bin/yt-dlp \
    --ytdl-format='bestvideo[height<=1080]+bestaudio/best' \
    --no-terminal --no-osc --cursor-autohide=always
Environment=DISPLAY=:0
Restart=always
```

`yt-dlp` is installed per-user (`pip3 install --user`), not from apt — the
packaged version is from 2022 and fails against today's YouTube. The Jetson has
no venv tooling, matching existing practice there.

### `robot-face/video.py` (new module)

The client for that socket, and the pure logic around it. Mirrors `teensy.py`:
one module, a custom error, no Flask imports.

- `play(target, start=None)`, `stop()`, `pause()`, `resume()`, `status()`
- `parse_start(value, url=None) -> int | None`
- `resolve(target) -> (url, title)` — a search phrase goes through
  `yt-dlp "ytsearch1:..."`; a URL is kept as given and its title fetched with
  `yt-dlp --print "%(title)s"`. If that title lookup fails but the target is a
  valid URL, playback still proceeds and the title comes from mpv's
  `media-title` once loaded. A search that resolves to nothing is an error —
  there is nothing to play.
- raises `VideoError` on a dead or silent socket; a short socket timeout, never
  an unbounded block

Resolving before playing means the panel and the agent normally know the title
up front, so neither opens a black window and hopes.

### Flask routes (`robot-face/app.py`)

All under `/api/video/`:

| Route | Body | Returns |
|---|---|---|
| `POST /api/video/play` | `{url_or_query, start?}` | `{ok, title, deferred}` |
| `POST /api/video/stop` | — | `{ok}` |
| `POST /api/video/pause` | — | `{ok}` |
| `POST /api/video/resume` | — | `{ok}` |
| `GET /api/video/status` | — | `{playing, paused, title, position, duration, deferred}` |

`VideoError` → 503. Unparseable input or an unresolvable target → 400 with the
reason. Bad or missing token → 403.

### Control panel (`robot-face/templates/control.html`)

A Video card: a URL-or-search box, a start-time box, Play; and while something
is playing, the title, position and duration with Pause and Stop. Polls
`/api/video/status` once a second only while playing.

### Agent tools (`voice-agent/agent.py`)

- `play_video(query_or_url, start_at=None)` — returns the title and the fact
  that it starts when the call ends
- `stop_video()`

After a successful `play_video`, the call must end. The tool sets a module-level
`asyncio.Event`; the entrypoint waits on it next to the silence watchdog, lets
her finish the sentence, then calls `ctx.shutdown()` — the same shutdown path as
the closing phrase. No new lifecycle.

### Wake word (`wake-word/wake_word.py`)

`WAKE_HEAD` stays `گردو`. The tail becomes a map:

| Tail | Action |
|---|---|
| `بابا` | start a call (unchanged) |
| `بسه`, `استاپ` | stop the video |

`score()` returns which action matched instead of a boolean. The new tails join
the filler grammar. **Stop tails are ignored unless a video is playing**, which
the detector learns from the status it already polls every two seconds — so they
cannot become a new false-positive source while the robot is idle.

## Behaviour

### Playing

A `POST /play` resolves the target, then either plays it or defers it.

### Calls take the screen

**Pause for a call is a stop plus a remembered position.** When the voice state
leaves idle, Flask reads the position from mpv, records `{url, position}` and
stops playback — the window disappears and the face is back for the call. When
the voice state returns to idle, Flask plays that URL from that position and
clears the record.

No window is minimised or raised, and resume reuses the play path. The cost is a
second or two of re-buffering after each call, accepted deliberately over
fighting the window manager.

### Deferral is a server rule, not a parameter

If `/play` arrives while the voice state is anything but idle, it is stored as
pending and started when the call ends. The agent therefore needs no special
case: it plays, receives `deferred: true`, and says so. The pending record and
the interrupted-video record are **one field**, so the two paths cannot both
fire.

### Truth lives in mpv

Position, title, duration and paused come from the socket on every `/status`.
Flask persists only what mpv cannot know: the pending or remembered video, in
`state.json`. A crashed or restarted mpv can never leave the panel showing a
video that is not playing.

### Other rules

- A new play request replaces whatever is playing. No queue.
- A video that ends on its own returns mpv to idle; the face is already back.
- Panel and agent conflicts are last-write-wins. `/status` is the truth. No
  locking.

## Configuration and secrets

| Where | Key | Purpose |
|---|---|---|
| `robot-face/config.json` (gitignored) | `video_token` | shared secret for off-box control |
| `voice-agent/.env` (gitignored) | `VIDEO_BASE_URL` | where the robot's Flask app is |
| `voice-agent/.env` (gitignored) | `VIDEO_API_TOKEN` | same secret |

The agent runs on the Mac, so it is not localhost and cannot use the
`local_only()` bypass. Requests carry `X-Video-Token`. The token is accepted
**only** on `/api/video/*`; everything else keeps session login. A one-time
setup step generates the value and puts it in both files. `.env.example` gains
the two names with empty values.

## Error handling

The kiosk has no console, so every failure is visible on the panel or in a log
file.

| Failure | Behaviour |
|---|---|
| mpv dead, socket missing | `VideoError` → 503, panel shows "player unreachable". `Restart=always` recovers it |
| `yt-dlp` cannot resolve (bad, private, age-gated, no search hits) | 400 with the reason; by voice she says she could not find it. Nothing plays, no window |
| `yt-dlp` rotting as YouTube changes | The likeliest long-term failure. Pinned install, documented update command, stated in the log entry |
| Video ends by itself | mpv returns to idle; `/status` reports not playing |
| Call starts while a video is loading | One "what should be playing" record; the pending video is the one deferred |
| Missing or wrong token | 403, logged with the source address, no detail in the response |

## Testing

Pure logic tested properly, hardware faked — the existing pattern.

- `parse_start()`: `90`, `1:30`, `1h2m3s`, `?t=42`, junk, and explicit beats URL
- `video.py` against a **fake socket**: well-formed JSON commands, replies
  parsed, dead socket raises `VideoError`, timeouts do not hang
  (`test_teensy.py`'s pattern)
- URL-versus-search classification
- Deferral: play while not idle defers; call end plays it; stop clears it; a
  second play replaces the pending one
- `score()`: `گردو بابا` → call, `گردو بسه` → stop, scattered tokens still
  rejected, over-long utterances still rejected, and the existing real-transcript
  cases unchanged
- Flask routes: session auth, token auth, neither; 400 on junk; 503 when the
  player is down

**Not covered automatically**, and to be checked on the bench: that mpv's window
actually covers the kiosk, and that the wake word hears `بسه` over video audio.

## Known constraints

- **Audio is 16 kHz.** Everything plays through the XVF3800, which is 16 kHz
  only. Speech is fine; music will sound like a phone call. No better output
  exists on the robot today.
- **CPU decode.** No hardware-accelerated path is assumed. 1080p on six A78
  cores is expected to be adequate; if it is not, the format cap drops to 720p.

## Follow-ups (not in this work)

- A second audio output if music quality matters.
- Hardware decode via the Tegra decoder, if CPU decode disappoints.
