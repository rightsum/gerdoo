# Video Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send a YouTube URL or search phrase — from the control panel or by asking Gerdoo — and it plays fullscreen over the kiosk face, pausing for calls and stopping on a spoken phrase.

**Architecture:** A long-lived `mpv --idle` user service owns the screen and is driven through its JSON IPC socket. `robot-face/video.py` is the socket client plus pure logic (start-time parsing, URL-vs-search, `yt-dlp` resolution). Flask exposes `/api/video/*`, which the panel and the agent both call; the agent authenticates with a shared token because it runs off-box on the Mac.

**Tech Stack:** Python 3.10 (Jetson, no venv — `pip3 install --user`), Flask 3, mpv 0.34 (apt), yt-dlp (pip, user), pytest, vanilla JS in the panel, livekit-agents 1.7 on the Mac.

**Spec:** `docs/superpowers/specs/2026-09-18-video-playback-design.md`

## Global Constraints

- **Public repo.** No names, hostnames, LAN IPs, SSH users, or API keys in any file or commit message. Secrets live in `robot-face/config.json` and `voice-agent/.env`, both gitignored.
- **Never hardcode device paths or indices.** Resolve by name or glob.
- **Robot has no venv tooling and no pyserial.** Standard library plus what is already installed.
- **All audio is 16 kHz** through the XVF3800. Do not add audio-device selection.
- **Systemd units use `%h` and `%t`**, never absolute home paths.
- **Tests:** `cd robot-face && python3 -m pytest tests -q` and `make -C voice-agent test`. Hardware is faked; no test may require mpv, a network, or the robot.
- **Kiosk has no console.** Every failure must surface in an HTTP response, the panel, or a log file.
- Commit after every task with a `feat:`/`test:`/`docs:` prefix and the repo's attribution trailer.

---

### Task 1: Start-time and target parsing (pure functions)

**Files:**
- Create: `robot-face/video.py`
- Test: `robot-face/tests/test_video.py`

**Interfaces:**
- Consumes: nothing
- Produces: `video.parse_start(value, url=None) -> int | None`, `video.looks_like_url(target) -> bool`, `video.VideoError`

- [ ] **Step 1: Write the failing tests**

```python
# robot-face/tests/test_video.py
import pytest

import video


# ---- start times ----

def test_plain_seconds():
    assert video.parse_start("90") == 90


def test_minutes_and_seconds():
    assert video.parse_start("1:30") == 90


def test_hours_minutes_seconds():
    assert video.parse_start("1:02:03") == 3723


def test_compact_form():
    assert video.parse_start("1h2m3s") == 3723


def test_blank_is_no_start():
    assert video.parse_start("") is None
    assert video.parse_start(None) is None


def test_junk_is_rejected():
    with pytest.raises(ValueError):
        video.parse_start("half past four")


def test_negative_is_rejected():
    with pytest.raises(ValueError):
        video.parse_start("-5")


def test_start_comes_from_the_url_when_not_given():
    url = "https://www.youtube.com/watch?v=abc123&t=42s"
    assert video.parse_start(None, url=url) == 42


def test_explicit_start_beats_the_url():
    url = "https://www.youtube.com/watch?v=abc123&t=42"
    assert video.parse_start("1:00", url=url) == 60


def test_youtu_be_short_link_start():
    assert video.parse_start(None, url="https://youtu.be/abc123?t=7") == 7


# ---- url vs search ----

def test_watch_url_is_a_url():
    assert video.looks_like_url("https://www.youtube.com/watch?v=abc123")


def test_short_link_is_a_url():
    assert video.looks_like_url("https://youtu.be/abc123")


def test_bare_words_are_a_search():
    assert not video.looks_like_url("googoosh talagh")


def test_a_word_with_a_dot_is_still_a_search():
    assert not video.looks_like_url("mr. bean cartoon")
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `cd robot-face && python3 -m pytest tests/test_video.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'video'`

- [ ] **Step 3: Write the module**

```python
# robot-face/video.py
"""
Playing a video on the robot's screen.

The player is one long-lived `mpv --idle` owned by video-player.service. Idle
means no window, so the kiosk face is visible whenever nothing is playing;
`loadfile` makes the window appear and `stop` makes it go away again.

This module is the client for mpv's JSON IPC socket, plus the pure logic around
it. It imports no Flask, the same way teensy.py does not — so all of it can be
tested without mpv, a network, or the robot.
"""

import json
import os
import re
import socket
import subprocess
import threading
import urllib.parse

SOCKET_PATH = os.environ.get(
    "MPV_SOCKET", f"/run/user/{os.getuid()}/gerdoo-mpv.sock")
TIMEOUT_S = 2.0
YTDLP = os.path.expanduser("~/.local/bin/yt-dlp")

_lock = threading.Lock()


class VideoError(RuntimeError):
    pass


_CLOCK = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{1,2})$")
_COMPACT = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?$")


def _from_text(text):
    text = text.strip().lower()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    m = _CLOCK.match(text)
    if m:
        h, mins, secs = m.group(1) or 0, m.group(2), m.group(3)
        return int(h) * 3600 + int(mins) * 60 + int(secs)
    m = _COMPACT.match(text)
    if m and any(m.groups()):
        h, mins, secs = (g or 0 for g in m.groups())
        return int(h) * 3600 + int(mins) * 60 + int(secs)
    raise ValueError(f"cannot read a start time from {text!r}")


def parse_start(value, url=None):
    """
    Seconds to start at, or None.

    Accepts what people actually paste: 90, 1:30, 1:02:03, 1h2m3s. An explicit
    value wins; otherwise a `t=` in the URL is used, because that is what you
    get when you copy a link at a timestamp.
    """
    if value is not None and str(value).strip():
        seconds = _from_text(str(value))
        if seconds is not None and seconds < 0:
            raise ValueError("start time cannot be negative")
        return seconds
    if url:
        query = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(query.query)
        raw = (params.get("t") or params.get("start") or [None])[0]
        if raw:
            try:
                return _from_text(raw.rstrip("s") if raw.endswith("s") else raw)
            except ValueError:
                return None
    return None


def looks_like_url(target):
    """True for something to play directly, False for something to search for."""
    if not target:
        return False
    parsed = urllib.parse.urlparse(target.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)
```

Note: `parse_start("-5")` reaches `_from_text`, where `"-5".isdigit()` is False and neither regex matches, so it raises `ValueError` — the negative guard is belt and braces for a future caller passing an int.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd robot-face && python3 -m pytest tests/test_video.py -q`
Expected: PASS, 13 tests

- [ ] **Step 5: Commit**

```bash
git add robot-face/video.py robot-face/tests/test_video.py
git commit -m "feat(video): parse start times and tell a URL from a search"
```

---

### Task 2: The mpv IPC client

**Files:**
- Modify: `robot-face/video.py`
- Test: `robot-face/tests/test_video.py`

**Interfaces:**
- Consumes: `video.VideoError`, `video.SOCKET_PATH`
- Produces: `video.command(*args) -> object`, `video.play_url(url, start=None)`, `video.stop()`, `video.pause()`, `video.resume()`, `video.status() -> dict` with keys `playing, paused, title, position, duration`

- [ ] **Step 1: Write the failing tests**

Append to `robot-face/tests/test_video.py`:

```python
import json
import socket
import threading

import pytest


class FakeMpv:
    """A unix socket that answers mpv's JSON IPC, for tests."""

    def __init__(self, tmp_path, replies=None, silent=False):
        self.path = str(tmp_path / "mpv.sock")
        self.replies = replies or {}
        self.silent = silent
        self.received = []
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.path)
        self.sock.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                buf = b""
                while b"\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        return
                    buf += chunk
                line = buf.split(b"\n", 1)[0]
                req = json.loads(line)
                self.received.append(req)
                if self.silent:
                    return
                name = req["command"][0]
                prop = req["command"][1] if len(req["command"]) > 1 else None
                key = f"{name}:{prop}" if name == "get_property" else name
                # An unrelated event first: the client must skip it.
                conn.sendall(json.dumps({"event": "playback-restart"}).encode() + b"\n")
                body = {"request_id": req.get("request_id", 0)}
                if key in self.replies:
                    body.update({"data": self.replies[key], "error": "success"})
                else:
                    body.update({"error": "property unavailable"})
                conn.sendall(json.dumps(body).encode() + b"\n")

    def close(self):
        self.sock.close()


@pytest.fixture
def fake_mpv(tmp_path, monkeypatch):
    made = []

    def make(replies=None, silent=False):
        m = FakeMpv(tmp_path, replies=replies, silent=silent)
        monkeypatch.setattr(video, "SOCKET_PATH", m.path)
        made.append(m)
        return m

    yield make
    for m in made:
        m.close()


def test_command_returns_the_data(fake_mpv):
    fake_mpv({"get_property:duration": 212.5})
    assert video.command("get_property", "duration") == 212.5


def test_command_skips_events_before_the_reply(fake_mpv):
    m = fake_mpv({"get_property:time-pos": 12.0})
    assert video.command("get_property", "time-pos") == 12.0
    assert m.received[0]["command"] == ["get_property", "time-pos"]


def test_unavailable_property_is_none_not_an_error(fake_mpv):
    fake_mpv({})
    assert video.command("get_property", "time-pos") is None


def test_missing_socket_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(video, "SOCKET_PATH", str(tmp_path / "nope.sock"))
    with pytest.raises(video.VideoError):
        video.command("get_property", "duration")


def test_a_silent_player_raises_rather_than_hanging(fake_mpv, monkeypatch):
    fake_mpv(silent=True)
    monkeypatch.setattr(video, "TIMEOUT_S", 0.3)
    with pytest.raises(video.VideoError):
        video.command("get_property", "duration")


def test_play_sends_loadfile_with_a_start(fake_mpv):
    m = fake_mpv({"loadfile": None})
    video.play_url("https://youtu.be/abc123", start=90)
    assert m.received[0]["command"] == [
        "loadfile", "https://youtu.be/abc123", "replace", "start=90"]


def test_play_without_a_start_sends_no_options(fake_mpv):
    m = fake_mpv({"loadfile": None})
    video.play_url("https://youtu.be/abc123")
    assert m.received[0]["command"] == [
        "loadfile", "https://youtu.be/abc123", "replace"]


def test_status_reports_idle_as_not_playing(fake_mpv):
    fake_mpv({"get_property:idle-active": True})
    st = video.status()
    assert st["playing"] is False
    assert st["title"] is None


def test_status_reports_a_playing_video(fake_mpv):
    fake_mpv({
        "get_property:idle-active": False,
        "get_property:media-title": "Talagh",
        "get_property:time-pos": 31.4,
        "get_property:duration": 212.5,
        "get_property:pause": False,
    })
    st = video.status()
    assert st == {"playing": True, "paused": False, "title": "Talagh",
                  "position": 31, "duration": 212}


def test_pause_and_resume_set_the_property(fake_mpv):
    m = fake_mpv({"set_property": None})
    video.pause()
    video.resume()
    assert m.received[0]["command"] == ["set_property", "pause", True]


def test_stop_sends_stop(fake_mpv):
    m = fake_mpv({"stop": None})
    video.stop()
    assert m.received[0]["command"] == ["stop"]
```

Note: the fake accepts one connection per command, which matches the client opening a fresh socket per call. `m.received[0]` is therefore the first command of that test.

- [ ] **Step 2: Run the tests and watch them fail**

Run: `cd robot-face && python3 -m pytest tests/test_video.py -q`
Expected: FAIL — `AttributeError: module 'video' has no attribute 'command'`

- [ ] **Step 3: Implement the client**

Append to `robot-face/video.py`:

```python
_request_id = 0


def _next_id():
    global _request_id
    _request_id += 1
    return _request_id


def command(*args):
    """
    Send one command to mpv and return its `data`, or None if unavailable.

    A fresh connection per command: mpv's socket is happy with it, and it means
    no shared reader that could hand one caller another's reply. Events arriving
    mid-exchange are skipped — only the reply carrying our request_id counts.

    Raises VideoError if the player is not there or does not answer. "Not
    playing" is never an error; it is a status.
    """
    req_id = _next_id()
    payload = json.dumps({"command": list(args), "request_id": req_id}) + "\n"

    with _lock:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(TIMEOUT_S)
        try:
            s.connect(SOCKET_PATH)
        except (FileNotFoundError, ConnectionRefusedError, OSError) as e:
            raise VideoError(f"player not running ({e.__class__.__name__})")
        try:
            s.sendall(payload.encode())
            buf = b""
            while True:
                try:
                    chunk = s.recv(4096)
                except socket.timeout:
                    raise VideoError("player did not answer")
                if not chunk:
                    raise VideoError("player closed the connection")
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    if not raw.strip():
                        continue
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    # Asynchronous events carry no request_id. Not ours.
                    if "event" in msg:
                        continue
                    if msg.get("request_id") != req_id:
                        continue
                    if msg.get("error") not in ("success", None):
                        return None        # e.g. property unavailable in idle
                    return msg.get("data")
        finally:
            s.close()


def play_url(url, start=None):
    """Load and play a URL, optionally from `start` seconds in."""
    args = ["loadfile", url, "replace"]
    if start:
        args.append(f"start={int(start)}")
    command(*args)


def stop():
    command("stop")


def pause():
    command("set_property", "pause", True)


def resume():
    command("set_property", "pause", False)


def _seconds(value):
    return int(value) if isinstance(value, (int, float)) else None


def status():
    """What is on screen right now, straight from the player."""
    if command("get_property", "idle-active"):
        return {"playing": False, "paused": False, "title": None,
                "position": None, "duration": None}
    return {
        "playing": True,
        "paused": bool(command("get_property", "pause")),
        "title": command("get_property", "media-title"),
        "position": _seconds(command("get_property", "time-pos")),
        "duration": _seconds(command("get_property", "duration")),
    }
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd robot-face && python3 -m pytest tests/test_video.py -q`
Expected: PASS, 24 tests

- [ ] **Step 5: Commit**

```bash
git add robot-face/video.py robot-face/tests/test_video.py
git commit -m "feat(video): talk to mpv over its IPC socket"
```

---

### Task 3: Resolving a target to a URL and a title

**Files:**
- Modify: `robot-face/video.py`
- Test: `robot-face/tests/test_video.py`

**Interfaces:**
- Consumes: `video.looks_like_url`, `video.VideoError`
- Produces: `video.resolve(target) -> (url, title)`, and `video._run(args) -> str` as the single subprocess seam tests replace

- [ ] **Step 1: Write the failing tests**

Append to `robot-face/tests/test_video.py`:

```python
def test_resolve_searches_for_bare_words(monkeypatch):
    calls = []

    def fake_run(args, timeout=None):
        calls.append(args)
        return "abc123|Googoosh - Talagh"

    monkeypatch.setattr(video, "_run", fake_run)
    url, title = video.resolve("googoosh talagh")
    assert url == "https://www.youtube.com/watch?v=abc123"
    assert title == "Googoosh - Talagh"
    assert "ytsearch1:googoosh talagh" in calls[0]


def test_resolve_keeps_a_url_and_fetches_its_title(monkeypatch):
    monkeypatch.setattr(video, "_run", lambda args, timeout=None: "Talagh")
    url, title = video.resolve("https://youtu.be/abc123")
    assert url == "https://youtu.be/abc123"
    assert title == "Talagh"


def test_resolve_plays_a_url_even_if_the_title_lookup_fails(monkeypatch):
    def boom(args, timeout=None):
        raise video.VideoError("yt-dlp failed")

    monkeypatch.setattr(video, "_run", boom)
    url, title = video.resolve("https://youtu.be/abc123")
    assert url == "https://youtu.be/abc123"
    assert title is None


def test_resolve_raises_when_a_search_finds_nothing(monkeypatch):
    monkeypatch.setattr(video, "_run", lambda args, timeout=None: "")
    with pytest.raises(video.VideoError):
        video.resolve("asdkjhasdkjh nonsense query")


def test_resolve_rejects_an_empty_target():
    with pytest.raises(ValueError):
        video.resolve("   ")
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `cd robot-face && python3 -m pytest tests/test_video.py -k resolve -q`
Expected: FAIL — `AttributeError: module 'video' has no attribute 'resolve'`

- [ ] **Step 3: Implement resolution**

Append to `robot-face/video.py`:

```python
RESOLVE_TIMEOUT_S = 25


def _run(args, timeout=RESOLVE_TIMEOUT_S):
    """Run yt-dlp and return its stdout. The single seam tests replace."""
    try:
        p = subprocess.run([YTDLP, *args], capture_output=True, text=True,
                           timeout=timeout)
    except FileNotFoundError:
        raise VideoError("yt-dlp is not installed")
    except subprocess.TimeoutExpired:
        raise VideoError("yt-dlp timed out")
    if p.returncode != 0:
        first = (p.stderr or "").strip().splitlines()
        raise VideoError(first[-1] if first else "yt-dlp failed")
    return p.stdout.strip()


def resolve(target):
    """
    (url, title) for something to play.

    A search phrase goes through yt-dlp's own search. A URL is kept exactly as
    given and only its title is looked up — and if that lookup fails, playback
    still proceeds with no title, because a URL the user pasted is a URL they
    want played.
    """
    target = (target or "").strip()
    if not target:
        raise ValueError("nothing to play")

    if looks_like_url(target):
        try:
            title = _run(["--no-playlist", "--print", "%(title)s", target]) or None
        except VideoError:
            title = None
        return target, title

    out = _run(["--no-playlist", "--print", "%(id)s|%(title)s",
                f"ytsearch1:{target}"])
    if not out or "|" not in out:
        raise VideoError(f"nothing found for {target!r}")
    video_id, _, title = out.partition("|")
    return f"https://www.youtube.com/watch?v={video_id}", title.strip() or None
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd robot-face && python3 -m pytest tests/test_video.py -q`
Expected: PASS, 29 tests

- [ ] **Step 5: Commit**

```bash
git add robot-face/video.py robot-face/tests/test_video.py
git commit -m "feat(video): resolve a URL or a search phrase with yt-dlp"
```

---

### Task 4: The player service

**Files:**
- Create: `robot-face/deploy/video-player.service`
- Modify: `robot-face/deploy/deploy.sh`, `robot-face/README.md`

**Interfaces:**
- Consumes: nothing
- Produces: a running `mpv --idle` with its socket at `%t/gerdoo-mpv.sock`, which Task 2's client connects to

- [ ] **Step 1: Write the unit**

```ini
# robot-face/deploy/video-player.service
[Unit]
Description=Video player — one idle mpv that owns the screen when a video plays
After=robot-face.service
Wants=robot-face.service

[Service]
Type=simple
Environment=DISPLAY=:0
# Idle with no window: the kiosk face stays visible until loadfile is sent, and
# stop takes the window away again. --fullscreen applies to the window when it
# does appear, so a video always covers the face.
ExecStart=/usr/bin/mpv --idle=yes --force-window=no --fullscreen \
    --input-ipc-server=%t/gerdoo-mpv.sock \
    --script-opts=ytdl_hook-ytdl_path=%h/.local/bin/yt-dlp \
    --ytdl-format=bestvideo[height<=1080]+bestaudio/best \
    --no-terminal --no-osc --cursor-autohide=always --keep-open=no
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

- [ ] **Step 2: Install the dependencies on the robot**

```bash
sudo apt-get install -y mpv
pip3 install --user --upgrade yt-dlp
~/.local/bin/yt-dlp --version      # expect a 2025-or-later date, not 2022
```

apt's `yt-dlp` is from 2022 and fails against today's YouTube; the pip build is the one mpv is pointed at.

- [ ] **Step 3: Install and start the unit**

```bash
scp robot-face/deploy/video-player.service <robot>:~/.config/systemd/user/
ssh <robot> 'systemctl --user daemon-reload && systemctl --user enable --now video-player'
ssh <robot> 'systemctl --user is-active video-player && ls -l /run/user/$(id -u)/gerdoo-mpv.sock'
```

Expected: `active`, and the socket exists.

- [ ] **Step 4: Verify by hand that a video covers the face**

```bash
ssh <robot> 'echo "{\"command\":[\"loadfile\",\"https://www.youtube.com/watch?v=aqz-KE-bpKQ\",\"replace\"]}" | socat - /run/user/$(id -u)/gerdoo-mpv.sock'
# look at the robot's screen: video, fullscreen, over the face
ssh <robot> 'echo "{\"command\":[\"stop\"]}" | socat - /run/user/$(id -u)/gerdoo-mpv.sock'
# the face is back
```

If `socat` is missing: `sudo apt-get install -y socat`. This is the bench check the spec says is not covered by tests. Record the outcome — if the window does not cover the kiosk, stop and report before continuing, because the whole approach rests on it.

- [ ] **Step 5: Add the unit to the deploy script**

In `robot-face/deploy/deploy.sh`, wherever `face-track.service` is copied and enabled, do the same for `video-player.service`. Follow the existing style exactly.

- [ ] **Step 6: Commit**

```bash
git add robot-face/deploy/video-player.service robot-face/deploy/deploy.sh robot-face/README.md
git commit -m "feat(video): an idle mpv service that owns the screen"
```

---

### Task 5: Flask routes and token auth

**Files:**
- Modify: `robot-face/app.py`
- Test: `robot-face/tests/test_video_routes.py`

**Interfaces:**
- Consumes: `video.resolve`, `video.parse_start`, `video.play_url`, `video.stop`, `video.pause`, `video.resume`, `video.status`, `video.VideoError`
- Produces: `POST /api/video/play` `{url_or_query, start?}` → `{ok, title, deferred}`; `POST /api/video/{stop,pause,resume}` → `{ok}`; `GET /api/video/status` → `{playing, paused, title, position, duration, deferred}`; helper `video_guard()`; state key `state["video_pending"]`

- [ ] **Step 1: Write the failing tests**

```python
# robot-face/tests/test_video_routes.py
import json

import pytest

import app as robot_app
import video


@pytest.fixture
def client(monkeypatch, tmp_path):
    robot_app.app.config["TESTING"] = True
    state = {"video_pending": None, "voice": "idle"}
    config = {"video_token": "s3cret", "moods": [], "secret_key": "x"}
    monkeypatch.setattr(robot_app, "load_state", lambda: dict(state))
    monkeypatch.setattr(robot_app, "save_state", lambda s: state.update(s))
    monkeypatch.setattr(robot_app, "load_config", lambda: dict(config))
    monkeypatch.setattr(robot_app, "broadcast", lambda payload: None)
    monkeypatch.setattr(video, "resolve",
                        lambda target: ("https://youtu.be/abc123", "Talagh"))
    monkeypatch.setattr(video, "play_url", lambda url, start=None: None)
    monkeypatch.setattr(video, "stop", lambda: None)
    monkeypatch.setattr(video, "status", lambda: {
        "playing": False, "paused": False, "title": None,
        "position": None, "duration": None})
    with robot_app.app.test_client() as c:
        c._state = state
        yield c


def hdr(token="s3cret"):
    return {"X-Video-Token": token, "Content-Type": "application/json"}


def test_play_requires_a_token(client):
    r = client.post("/api/video/play", json={"url_or_query": "x"})
    assert r.status_code == 403


def test_play_rejects_a_wrong_token(client):
    r = client.post("/api/video/play", json={"url_or_query": "x"},
                    headers=hdr("nope"))
    assert r.status_code == 403


def test_play_starts_a_video(client):
    r = client.post("/api/video/play",
                    data=json.dumps({"url_or_query": "talagh"}), headers=hdr())
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["title"] == "Talagh"
    assert body["deferred"] is False


def test_play_during_a_call_is_deferred(client):
    client._state["voice"] = "listening"
    r = client.post("/api/video/play",
                    data=json.dumps({"url_or_query": "talagh"}), headers=hdr())
    assert r.get_json()["deferred"] is True
    assert client._state["video_pending"]["url"] == "https://youtu.be/abc123"


def test_a_second_play_replaces_the_pending_one(client, monkeypatch):
    client._state["voice"] = "listening"
    client.post("/api/video/play", data=json.dumps({"url_or_query": "one"}),
                headers=hdr())
    monkeypatch.setattr(video, "resolve",
                        lambda target: ("https://youtu.be/second", "Second"))
    client.post("/api/video/play", data=json.dumps({"url_or_query": "two"}),
                headers=hdr())
    assert client._state["video_pending"]["url"] == "https://youtu.be/second"


def test_play_rejects_a_bad_start_time(client):
    r = client.post("/api/video/play",
                    data=json.dumps({"url_or_query": "x", "start": "half four"}),
                    headers=hdr())
    assert r.status_code == 400


def test_play_reports_a_resolve_failure(client, monkeypatch):
    def boom(target):
        raise video.VideoError("nothing found")

    monkeypatch.setattr(video, "resolve", boom)
    r = client.post("/api/video/play", data=json.dumps({"url_or_query": "zzz"}),
                    headers=hdr())
    assert r.status_code == 400
    assert "nothing found" in r.get_json()["error"]


def test_a_dead_player_is_a_503(client, monkeypatch):
    def boom(url, start=None):
        raise video.VideoError("player not running")

    monkeypatch.setattr(video, "play_url", boom)
    r = client.post("/api/video/play", data=json.dumps({"url_or_query": "x"}),
                    headers=hdr())
    assert r.status_code == 503


def test_stop_clears_a_pending_video(client):
    client._state["video_pending"] = {"url": "u", "title": "t", "start": 5}
    r = client.post("/api/video/stop", headers=hdr())
    assert r.status_code == 200
    assert client._state["video_pending"] is None


def test_status_includes_deferred(client):
    client._state["video_pending"] = {"url": "u", "title": "t", "start": 0}
    r = client.get("/api/video/status", headers=hdr())
    assert r.get_json()["deferred"] is True
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `cd robot-face && python3 -m pytest tests/test_video_routes.py -q`
Expected: FAIL — 404s, because the routes do not exist.

- [ ] **Step 3: Add the routes**

In `robot-face/app.py`, add `import video` next to `import teensy`, then add this section after the voice routes:

```python
# ---- Video ----
# The agent runs on another machine, so local_only() cannot be the gate here.
# A shared token opens these routes and ONLY these routes; everything else keeps
# session login. The token lives in config.json, which is gitignored.
def video_guard():
    """None to proceed, or a response to abort with."""
    token = load_config().get("video_token", "")
    sent = request.headers.get("X-Video-Token", "")
    if token and sent and sent == token:
        return None
    if logged_in() or local_only():
        return None
    app.logger.warning("video: rejected request from %s", request.remote_addr)
    return jsonify(error="forbidden"), 403


def _pending():
    return load_state().get("video_pending")


def _set_pending(record):
    s = load_state()
    s["video_pending"] = record
    s["updated"] = time.time()
    save_state(s)


@app.route("/api/video/play", methods=["POST"])
def api_video_play():
    guard = video_guard()
    if guard:
        return guard
    data = request.get_json(force=True, silent=True) or {}
    target = (data.get("url_or_query") or "").strip()
    if not target:
        return jsonify(error="nothing to play"), 400
    try:
        url, title = video.resolve(target)
        start = video.parse_start(data.get("start"), url=url)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except video.VideoError as e:
        return jsonify(error=str(e)), 400

    # Deferral is a rule, not a parameter: anything asked for during a call
    # starts when the call ends. One record serves both this and a video
    # interrupted BY a call, so the two can never both fire.
    if load_state().get("voice", "idle") != "idle":
        _set_pending({"url": url, "title": title, "start": start or 0})
        return jsonify(ok=True, title=title, deferred=True)

    try:
        video.play_url(url, start=start)
    except video.VideoError as e:
        return jsonify(error=str(e)), 503
    _set_pending(None)
    return jsonify(ok=True, title=title, deferred=False)


@app.route("/api/video/stop", methods=["POST"])
def api_video_stop():
    guard = video_guard()
    if guard:
        return guard
    _set_pending(None)
    try:
        video.stop()
    except video.VideoError as e:
        return jsonify(error=str(e)), 503
    return jsonify(ok=True)


@app.route("/api/video/<action>", methods=["POST"])
def api_video_pause_resume(action):
    guard = video_guard()
    if guard:
        return guard
    if action not in ("pause", "resume"):
        return jsonify(error="unknown action"), 400
    try:
        getattr(video, action)()
    except video.VideoError as e:
        return jsonify(error=str(e)), 503
    return jsonify(ok=True)


@app.route("/api/video/status")
def api_video_status():
    guard = video_guard()
    if guard:
        return guard
    try:
        st = video.status()
    except video.VideoError as e:
        return jsonify(error=str(e), playing=False, deferred=bool(_pending())), 503
    st["deferred"] = bool(_pending())
    return jsonify(st)
```

Route order matters: `/api/video/stop` is declared before `/api/video/<action>` so the specific rule wins.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd robot-face && python3 -m pytest tests -q`
Expected: PASS — the new file plus every existing test.

- [ ] **Step 5: Generate the token on the robot**

```bash
ssh <robot> 'python3 - <<EOF
import json, os, secrets
p = os.path.expanduser("~/robot-face/config.json")
cfg = json.load(open(p))
cfg.setdefault("video_token", secrets.token_urlsafe(24))
json.dump(cfg, open(p, "w"), indent=2)
print(cfg["video_token"])
EOF'
```

Keep that value for Task 9. It must never appear in a commit.

- [ ] **Step 6: Commit**

```bash
git add robot-face/app.py robot-face/tests/test_video_routes.py
git commit -m "feat(video): play, stop and status endpoints with token auth"
```

---

### Task 6: Calls take the screen

**Files:**
- Modify: `robot-face/app.py` (`_set_voice`)
- Test: `robot-face/tests/test_video_routes.py`

**Interfaces:**
- Consumes: `_set_pending`, `_pending`, `video.status`, `video.stop`, `video.play_url`
- Produces: the pause-for-a-call behaviour; no new public names

- [ ] **Step 1: Write the failing tests**

Append to `robot-face/tests/test_video_routes.py`:

```python
def test_a_call_stops_a_playing_video_and_remembers_where(client, monkeypatch):
    stopped = []
    monkeypatch.setattr(video, "status", lambda: {
        "playing": True, "paused": False, "title": "Talagh",
        "position": 42, "duration": 200})
    monkeypatch.setattr(video, "stop", lambda: stopped.append(True))
    monkeypatch.setattr(robot_app, "_current_url", lambda: "https://youtu.be/abc123")

    robot_app._set_voice("connecting")

    assert stopped == [True]
    assert client._state["video_pending"] == {
        "url": "https://youtu.be/abc123", "title": "Talagh", "start": 42}


def test_the_call_ending_resumes_the_video(client, monkeypatch):
    played = []
    client._state["voice"] = "listening"
    client._state["video_pending"] = {
        "url": "https://youtu.be/abc123", "title": "Talagh", "start": 42}
    monkeypatch.setattr(video, "play_url",
                        lambda url, start=None: played.append((url, start)))

    robot_app._set_voice("idle")

    assert played == [("https://youtu.be/abc123", 42)]
    assert client._state["video_pending"] is None


def test_nothing_playing_means_nothing_to_remember(client, monkeypatch):
    monkeypatch.setattr(video, "status", lambda: {
        "playing": False, "paused": False, "title": None,
        "position": None, "duration": None})
    robot_app._set_voice("connecting")
    assert client._state["video_pending"] is None


def test_a_dead_player_does_not_break_a_call(client, monkeypatch):
    def boom():
        raise video.VideoError("player not running")

    monkeypatch.setattr(video, "status", boom)
    robot_app._set_voice("connecting")          # must not raise
    assert client._state["voice"] == "connecting"
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `cd robot-face && python3 -m pytest tests/test_video_routes.py -k call -q`
Expected: FAIL — `AttributeError: module 'app' has no attribute '_current_url'`

- [ ] **Step 3: Implement it**

In `robot-face/app.py`, add above `_set_voice`:

```python
def _current_url():
    """The URL mpv is playing, for remembering across a call."""
    return video.command("get_property", "path")


def _video_yield_to_call():
    """
    Stop a playing video and remember where it was.

    Pausing would leave mpv's window on screen covering the face, so a call
    would happen behind a frozen frame. Stopping takes the window away; the
    position comes back on resume. The cost is a second of re-buffering
    afterwards, which is cheaper than juggling windows with the WM.
    """
    try:
        st = video.status()
        if not st.get("playing"):
            return
        url = _current_url()
        if not url:
            return
        _set_pending({"url": url, "title": st.get("title"),
                      "start": st.get("position") or 0})
        video.stop()
    except video.VideoError as e:
        app.logger.warning("video: could not pause for the call (%s)", e)


def _video_resume_after_call():
    record = _pending()
    if not record:
        return
    try:
        video.play_url(record["url"], start=record.get("start") or None)
        _set_pending(None)
    except video.VideoError as e:
        app.logger.warning("video: could not resume after the call (%s)", e)
```

Then in `_set_voice`, before the state is written:

```python
def _set_voice(state, detail=""):
    """Update voice state and push it to the face over the existing SSE."""
    was = load_state().get("voice", "idle")
    # The screen belongs to the call: a video steps aside when one starts and
    # comes back when it ends. This is also what makes a video requested DURING
    # a call start afterwards — both use the same pending record.
    if state != "idle" and was == "idle":
        _video_yield_to_call()
    s = load_state()
    s["voice"] = state
    s["voice_detail"] = detail
    s["updated"] = time.time()
    save_state(s)
    broadcast(s)
    if state == "idle" and was != "idle":
        _video_resume_after_call()
    return s
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd robot-face && python3 -m pytest tests -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add robot-face/app.py robot-face/tests/test_video_routes.py
git commit -m "feat(video): a call takes the screen, the video resumes after"
```

---

### Task 7: The panel's Video card

**Files:**
- Modify: `robot-face/templates/control.html`

**Interfaces:**
- Consumes: `/api/video/play`, `/api/video/stop`, `/api/video/pause`, `/api/video/resume`, `/api/video/status`; the page's existing `api()` and `showToast()` helpers
- Produces: no new server interface

- [ ] **Step 1: Add the card markup**

Insert after the Voice `</section>`:

```html
    <!-- ---------------- Video ---------------- -->
    <section class="panel" id="video-panel">
      <div class="panel-head">
        <h2>Video</h2>
        <span class="status" id="vid-status"><span class="led"></span><span id="vid-status-text">idle</span></span>
      </div>
      <div class="panel-body">
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <input id="vid-target" placeholder="YouTube URL or search"
                 style="flex:1;min-width:180px;background:#1a2438;color:#e0e6f0;
                        border:1px solid #2a3a5a;border-radius:6px;padding:8px;font-size:13px">
          <input id="vid-start" placeholder="start (1:30)"
                 style="width:110px;background:#1a2438;color:#e0e6f0;
                        border:1px solid #2a3a5a;border-radius:6px;padding:8px;font-size:13px">
          <button id="vid-play" style="cursor:pointer;border:1px solid #2a3a5a;border-radius:6px;
                  background:#1a2438;color:#e0e6f0;padding:8px 14px;font-size:13px">Play</button>
        </div>
        <p class="hint" id="vid-hint">Plays on the robot's screen. A call pauses it;
          it resumes when the call ends. Say <span style="font-family:ui-monospace,monospace">گردو بسه</span> to stop.</p>
        <div id="vid-now" style="display:none;margin-top:10px">
          <div id="vid-title" style="font-size:13px;color:#e0e6f0;margin-bottom:6px"></div>
          <div style="display:flex;gap:8px;align-items:center">
            <span id="vid-time" style="font-size:12px;color:#8493b3;font-family:ui-monospace,monospace">0:00 / 0:00</span>
            <span style="flex:1"></span>
            <button id="vid-pause" style="cursor:pointer;border:1px solid #2a3a5a;border-radius:6px;
                    background:#1a2438;color:#e0e6f0;padding:6px 12px;font-size:13px">Pause</button>
            <button id="vid-stop" style="cursor:pointer;border:1px solid #2a3a5a;border-radius:6px;
                    background:#1a2438;color:#e0e6f0;padding:6px 12px;font-size:13px">Stop</button>
          </div>
        </div>
      </div>
    </section>
```

- [ ] **Step 2: Let `api()` carry a body**

The page's helper is `async function api(path, method)` at `control.html:335` and sends no body, so a POST with JSON needs it extended. Additive — every existing call keeps working:

```javascript
    async function api(path, method, body) {
      const opts = { method: method || 'GET' };
      if (body !== undefined) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(body);
      }
      const r = await fetch(path, opts);
      if (r.status === 401) { location.href = '/login'; throw new Error('auth'); }
      const body_ = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body_.message || body_.error || 'request failed');
      return body_;
    }
```

- [ ] **Step 3: Add the JavaScript**

Insert before `// ---- Battery ----`:

```javascript
    // ---- Video ----
    const vidTarget = document.getElementById('vid-target');
    const vidStart  = document.getElementById('vid-start');
    const vidNow    = document.getElementById('vid-now');
    const vidTitle  = document.getElementById('vid-title');
    const vidTime   = document.getElementById('vid-time');
    const vidStatus = document.getElementById('vid-status');
    const vidText   = document.getElementById('vid-status-text');
    const vidPause  = document.getElementById('vid-pause');
    let vidPlaying = false;

    function clock(s) {
      if (s == null) return '0:00';
      const m = Math.floor(s / 60), r = Math.floor(s % 60);
      return m + ':' + String(r).padStart(2, '0');
    }

    function vidReflect(st) {
      vidPlaying = !!(st && st.playing);
      vidStatus.classList.toggle('on', vidPlaying);
      vidText.textContent = st && st.deferred ? 'after the call'
                          : (vidPlaying ? (st.paused ? 'paused' : 'playing') : 'idle');
      vidNow.style.display = vidPlaying ? 'block' : 'none';
      if (vidPlaying) {
        vidTitle.textContent = st.title || '';
        vidTime.textContent = clock(st.position) + ' / ' + clock(st.duration);
        vidPause.textContent = st.paused ? 'Resume' : 'Pause';
      }
    }

    document.getElementById('vid-play').addEventListener('click', async () => {
      const target = vidTarget.value.trim();
      if (!target) return;
      try {
        const d = await api('/api/video/play', 'POST',
                            { url_or_query: target, start: vidStart.value.trim() });
        showToast(d.deferred ? 'Plays when the call ends' : ('Playing ' + (d.title || '')));
        vidTarget.value = '';
        refreshVideo();
      } catch (e) { showToast(e.message); }
    });

    vidPause.addEventListener('click', async () => {
      try {
        const st = await api('/api/video/status');
        await api('/api/video/' + (st.paused ? 'resume' : 'pause'), 'POST');
        refreshVideo();
      } catch (e) { showToast(e.message); }
    });

    document.getElementById('vid-stop').addEventListener('click', async () => {
      try { await api('/api/video/stop', 'POST'); showToast('Stopped'); refreshVideo(); }
      catch (e) { showToast(e.message); }
    });

    async function refreshVideo() {
      try { vidReflect(await api('/api/video/status')); }
      catch { vidText.textContent = 'unreachable'; }
    }

    refreshVideo();
    // One second while something is playing, so the position moves; slower when
    // idle, because then there is nothing to watch.
    setInterval(() => { if (vidPlaying) refreshVideo(); }, 1000);
    setInterval(refreshVideo, 5000);
```

- [ ] **Step 4: Check the template still parses**

Run: `cd robot-face && python3 -c "import jinja2,pathlib; jinja2.Environment().parse(pathlib.Path('templates/control.html').read_text()); print('template ok')"`
Expected: `template ok`. (`node --check` cannot be used — it chokes on Jinja tags.)

- [ ] **Step 5: Deploy and look at it**

```bash
scp robot-face/templates/control.html <robot>:~/robot-face/templates/
ssh <robot> 'systemctl --user restart robot-face'
```

Jinja caches templates, so the restart is not optional. Open the panel, play something, confirm the title and clock appear and Stop works.

- [ ] **Step 6: Commit**

```bash
git add robot-face/templates/control.html
git commit -m "feat(video): a Video card on the control panel"
```

---

### Task 8: "گردو بسه" stops the video

**Files:**
- Create: `wake-word/phrases.py`, `wake-word/tests/test_phrases.py`
- Modify: `wake-word/wake_word.py`

**Interfaces:**
- Consumes: `/api/video/status`, `/api/video/stop`
- Produces: `phrases.WAKE_HEAD`, `phrases.WAKE_TAILS: dict[str, str]`, `phrases.WAKE_PHRASES: list[str]`, `phrases.MAX_UTTERANCE_TOKENS`, `phrases.score(result) -> (action, confidence, text)` where `action` is `"call"`, `"stop"` or `None`. `wake_word.py` re-exports them by importing from `phrases`.

**Why a separate module:** `wake_word.py` imports numpy, scipy and vosk at module scope, and none of those are installed on the development machine — so a test importing it cannot run here at all. The matching logic has no need of them. Moving it into `phrases.py` makes the part worth testing testable, which is the same reason `face_tracking.py` is separate from `face_tracker.py`.

- [ ] **Step 1: Write the failing tests**

```python
# wake-word/tests/test_phrases.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import phrases


def result(text, conf=0.9):
    return {"text": text,
            "result": [{"word": w, "conf": conf} for w in text.split()]}


def test_the_call_phrase_asks_for_a_call():
    action, conf, _ = phrases.score(result("گردو بابا"))
    assert action == "call"
    assert conf == 0.9


def test_the_stop_phrase_asks_for_a_stop():
    action, _, _ = phrases.score(result("گردو بسه"))
    assert action == "stop"


def test_the_english_stop_phrase_also_works():
    action, _, _ = phrases.score(result("گردو استاپ"))
    assert action == "stop"


def test_the_head_word_alone_does_nothing():
    action, _, _ = phrases.score(result("گردو"))
    assert action is None


def test_a_bare_tail_does_nothing():
    action, _, _ = phrases.score(result("بابا"))
    assert action is None


def test_scattered_words_are_rejected():
    action, _, _ = phrases.score(result("بابا نیست گردو آقا"))
    assert action is None


def test_a_long_utterance_is_rejected():
    long_text = "بابا میکنه الان گردو بابا میکنه گرم خیلی"
    action, _, _ = phrases.score(result(long_text))
    assert action is None


def test_a_short_call_with_one_filler_word_still_counts():
    action, _, _ = phrases.score(result("الان گردو بابا"))
    assert action == "call"


def test_confidence_is_averaged_over_the_phrase_only():
    r = {"text": "الان گردو بابا",
         "result": [{"word": "الان", "conf": 0.1},
                    {"word": "گردو", "conf": 0.8},
                    {"word": "بابا", "conf": 1.0}]}
    action, conf, _ = phrases.score(r)
    assert action == "call"
    assert abs(conf - 0.9) < 1e-6
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `cd wake-word && python3 -m pytest tests -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'phrases'`

- [ ] **Step 3: Create `phrases.py` with the matching logic**

Move the constants and `score()` out of `wake_word.py` into a new module that imports nothing outside the standard library:

```python
# wake-word/phrases.py
"""
What the robot listens for, and how a decoder result is judged.

Separate from wake_word.py because that module imports numpy, scipy and vosk at
import time — so none of this could be tested without an audio stack installed.
The matching rules are the part most worth testing: every false positive this
project has had was a bug in here, not in the audio.
"""

import json

WAKE_HEAD = "گردو"   # the discriminating half; a bare tail is far too common

# What may follow the head, and what each one asks for. The head is what keeps
# false positives down, so every command shares it — one grammar, one adjacency
# rule, two actions.
WAKE_TAILS = {
    "بابا": "call",     # start a conversation
    "بسه": "stop",      # "enough" — stop the video
    "استاپ": "stop",    # "stop", as commonly borrowed into Persian
}

WAKE_PHRASE = f"{WAKE_HEAD} بابا"
WAKE_PHRASES = [f"{WAKE_HEAD} {tail}" for tail in WAKE_TAILS]

# Longest utterance still treated as someone addressing the robot. Above this it
# is conversation, not a command.
MAX_UTTERANCE_TOKENS = 4


def score(result):
    """
    (action, mean_confidence, text) for one final Vosk result.

    `action` is "call", "stop", or None. Confidence is averaged over the two
    words of the phrase only — surrounding filler otherwise drags it around.

    The two words must be ADJACENT. Merely containing both somewhere is not
    enough: under the filler grammar, ordinary conversation produced hits like
    "بابا نیست اون خانم گردو آقا", which contain both words scattered among
    filler. Roughly a third of all triggers were this.
    """
    text = result.get("text", "").strip()
    tokens = text.split()

    # Addressing the robot is a SHORT utterance. The false positives in the log
    # ran 7 to 15 words, while every genuine call was 2 or 3.
    if len(tokens) > MAX_UTTERANCE_TOKENS:
        return None, 0.0, text

    idx, action = None, None
    for i in range(len(tokens) - 1):
        if tokens[i] == WAKE_HEAD and tokens[i + 1] in WAKE_TAILS:
            idx, action = i, WAKE_TAILS[tokens[i + 1]]
            break
    if idx is None:
        return None, 0.0, text

    # Score only the two words of the phrase itself, positionally — not every
    # occurrence of either word in the utterance.
    words = result.get("result", [])
    if len(words) == len(tokens) and idx + 1 < len(words):
        pair = words[idx:idx + 2]
    else:
        pair = [w for w in words
                if w.get("word") == WAKE_HEAD or w.get("word") in WAKE_TAILS]
    if not pair:
        return action, 1.0, text        # no per-word data; grammar match alone
    conf = sum(w.get("conf", 0.0) for w in pair) / len(pair)
    return action, conf, text


def grammar(filler_words):
    """Vosk decoder grammar: every command phrase, plus competitors."""
    return json.dumps(WAKE_PHRASES + list(filler_words) + ["[unk]"],
                      ensure_ascii=False)


def strict_grammar():
    return json.dumps(WAKE_PHRASES + ["[unk]"], ensure_ascii=False)
```

- [ ] **Step 4: Point `wake_word.py` at it**

Delete `WAKE_PHRASE`, `WAKE_HEAD`, `MAX_UTTERANCE_TOKENS` and the whole of `score()` from `wake_word.py`, and replace the grammar constants with calls into the new module. Keep `FILLER_WORDS` where it is — it is a tuning table, not logic:

```python
from phrases import (WAKE_HEAD, WAKE_PHRASE, WAKE_PHRASES, WAKE_TAILS,
                     MAX_UTTERANCE_TOKENS, score)

...

GRAMMAR_STRICT = phrases.strict_grammar()
GRAMMAR_FILLER = phrases.grammar(FILLER_WORDS)
```

Import the module as well as the names (`import phrases`), since the grammar helpers are called through it.

- [ ] **Step 5: Run the tests and watch them pass**

Run: `cd wake-word && python3 -m pytest tests -q`
Expected: PASS, 9 tests

- [ ] **Step 6: Update every caller of `score()`**

`score()` now returns an action where it returned a bool. Fix all three call sites:

In `run_replay()`:

```python
        action, conf, text = score(json.loads(rec.Result()))
        if action and conf >= threshold:
```

In the live loop, replace `matched, conf, text = score(...)` and its `if not (matched and conf >= args.threshold): continue` with:

```python
                action, conf, text = score(json.loads(rec.Result()))
                if text and args.verbose:
                    print(f"  heard: {text}   conf={conf:.2f}", flush=True)
                if not (action and conf >= args.threshold):
                    continue
```

Add the video helpers next to `voice_disabled()`:

```python
def video_playing(base_url, timeout=3.0):
    """True if something is on the robot's screen right now."""
    try:
        with urllib.request.urlopen(f"{base_url}/api/video/status",
                                    timeout=timeout) as r:
            return bool(json.loads(r.read()).get("playing"))
    except Exception:
        return False


def stop_video(base_url, timeout=5.0):
    req = urllib.request.Request(f"{base_url}/api/video/stop", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception as e:
        print(f"  video stop failed: {e}", file=sys.stderr)
        return False
```

Then, in the live loop immediately after the cooldown check and the trigger log line, handle a stop before anything else happens — no chime, no session:

```python
                # "گردو بسه" only means anything while a video is playing.
                # Ignoring it otherwise keeps a second phrase from becoming a
                # second source of false positives when the robot is idle.
                if action == "stop":
                    if args.voice_url and video_playing(args.voice_url):
                        stop_video(args.voice_url)
                        print("  video stopped by voice", flush=True)
                        if logfh:
                            logfh.write("  video stopped by voice\n")
                    else:
                        print("  stop phrase, but nothing is playing", flush=True)
                    rec.Reset()
                    last_fire = time.time()
                    continue
```

- [ ] **Step 7: Run the whole suite and a replay**

Run: `cd wake-word && python3 -m pytest tests -q`
Expected: PASS

Then, on the robot, against a real recording:

```bash
ssh <robot> 'cd ~/wake-word && python3 wake_word.py --replay ambient.wav --threshold 0.5'
```

Expected: a hit count in the same range as before the change. A large jump means the new tails are firing on ordinary speech — report it rather than tuning the threshold to hide it.

- [ ] **Step 8: Deploy and commit**

```bash
scp wake-word/wake_word.py wake-word/phrases.py <robot>:~/wake-word/
ssh <robot> 'systemctl --user restart wake-word && systemctl --user is-active wake-word'
git add wake-word/wake_word.py wake-word/phrases.py wake-word/tests/test_phrases.py
git commit -m "feat(wake): گردو بسه stops the video"
```

`phrases.py` must be copied too — without it the service fails to import and the robot goes deaf.

---

### Task 9: Agent tools

**Files:**
- Create: `voice-agent/video_control.py`, `voice-agent/tests/test_video_control.py`
- Modify: `voice-agent/agent.py`, `voice-agent/.env.example`

**Interfaces:**
- Consumes: `/api/video/play`, `/api/video/stop` with the `X-Video-Token` header
- Produces: `video_control.play(target, start=None) -> dict`, `video_control.stop() -> dict`, agent tools `play_video`, `stop_video`, and `agent.end_call` (an `asyncio.Event`)

- [ ] **Step 1: Write the failing tests**

```python
# voice-agent/tests/test_video_control.py
import json

import video_control


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = json.dumps(body).encode()
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_play_posts_the_target_and_the_token(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["token"] = req.headers.get("X-video-token")
        seen["body"] = json.loads(req.data)
        return FakeResponse({"ok": True, "title": "Talagh", "deferred": True})

    monkeypatch.setattr(video_control.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(video_control, "BASE_URL", "http://robot:8080")
    monkeypatch.setattr(video_control, "TOKEN", "s3cret")

    out = video_control.play("talagh", start="1:30")
    assert out["title"] == "Talagh"
    assert out["deferred"] is True
    assert seen["url"] == "http://robot:8080/api/video/play"
    assert seen["token"] == "s3cret"
    assert seen["body"] == {"url_or_query": "talagh", "start": "1:30"}


def test_play_reports_an_error_instead_of_raising(monkeypatch):
    def boom(req, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr(video_control.urllib.request, "urlopen", boom)
    out = video_control.play("talagh")
    assert out["ok"] is False
    assert "connection refused" in out["error"]


def test_play_without_configuration_says_so(monkeypatch):
    monkeypatch.setattr(video_control, "BASE_URL", "")
    out = video_control.play("talagh")
    assert out["ok"] is False
    assert "not configured" in out["error"]


def test_stop_posts_to_the_stop_endpoint(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        return FakeResponse({"ok": True})

    monkeypatch.setattr(video_control.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(video_control, "BASE_URL", "http://robot:8080")
    monkeypatch.setattr(video_control, "TOKEN", "s3cret")
    assert video_control.stop()["ok"] is True
    assert seen["url"] == "http://robot:8080/api/video/stop"
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `make -C voice-agent test`
Expected: FAIL — `ModuleNotFoundError: No module named 'video_control'`

- [ ] **Step 3: Write the client**

```python
# voice-agent/video_control.py
"""
Asking the robot to play a video.

The agent runs on another machine, so this is an HTTP call to the robot's Flask
app authenticated with a shared token. Like web_search, it NEVER raises: a
failure here must become something the robot can say, not a dead turn.
"""

import json
import os
import urllib.error
import urllib.request

BASE_URL = os.environ.get("VIDEO_BASE_URL", "").rstrip("/")
TOKEN = os.environ.get("VIDEO_API_TOKEN", "")
TIMEOUT_S = 30


def _post(path, body=None):
    if not BASE_URL or not TOKEN:
        return {"ok": False,
                "error": "video control is not configured (VIDEO_BASE_URL / "
                         "VIDEO_API_TOKEN)"}
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json", "X-Video-Token": TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return {"ok": False, "error": json.loads(e.read()).get("error", str(e))}
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def play(target, start=None):
    body = {"url_or_query": target}
    if start:
        body["start"] = start
    return _post("/api/video/play", body)


def stop():
    return _post("/api/video/stop")
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `make -C voice-agent test`
Expected: PASS

- [ ] **Step 5: Add the tools and the end-of-call signal**

In `voice-agent/agent.py`, add `import video_control` beside `import web_search`, and after `look_it_up`:

```python
# Set by play_video. The entrypoint waits on it and shuts the session down once
# she has finished speaking: the video wants the screen and the speaker, and a
# call sitting on top of it would both compete for audio and hold the face.
end_call = asyncio.Event()


@function_tool
async def play_video(context: RunContext, query_or_url: str,
                     start_at: str = "") -> str:
    """
    Play a YouTube video on the robot's own screen.

    Use it when asked to play, show, or put on a video, a song, a clip or a
    film. The conversation ENDS when you do this — the video takes the screen —
    so say one short sentence confirming what you are playing, and nothing else
    afterwards.

    Args:
        query_or_url: A YouTube URL, or what to search for. A search phrase
            works best as the words a person would type: artist and title.
        start_at: Optional point to start at, like "1:30" or "90". Leave empty
            to start at the beginning.
    """
    out = await asyncio.to_thread(video_control.play, query_or_url,
                                  start_at or None)
    _trace(f"PLAY VIDEO {query_or_url!r} -> {out}")
    if not out.get("ok"):
        return f"Could not play it: {out.get('error', 'unknown error')}"
    end_call.set()
    title = out.get("title") or "it"
    return (f"Playing {title} now. Tell the user in one short sentence, then "
            "stop talking — the call is ending and the video is starting.")


@function_tool
async def stop_video(context: RunContext) -> str:
    """
    Stop whatever video is playing on the robot's screen.

    Use it when asked to stop, close, or turn off the video.
    """
    out = await asyncio.to_thread(video_control.stop)
    _trace(f"STOP VIDEO -> {out}")
    if not out.get("ok"):
        return f"Could not stop it: {out.get('error', 'unknown error')}"
    return "Stopped."
```

Register them: `tools=[look_it_up, what_time_is_it, play_video, stop_video]`.

Clear the flag at the top of `entrypoint`, right after `_trace("entrypoint ENTER")` — the worker process is reused between jobs, so a set flag would end the next call instantly:

```python
    end_call.clear()
```

And add the waiter next to the silence watchdog, after `watch = asyncio.create_task(_watch_silence())`:

```python
    async def _watch_end_call():
        """A video was requested. Let her finish the sentence, then hang up."""
        await end_call.wait()
        while session.agent_state in ("speaking", "thinking"):
            await asyncio.sleep(0.2)
        _trace("ending the call so the video can start")
        ctx.shutdown(reason="video requested")
        finished.set()

    ender = asyncio.create_task(_watch_end_call())
    _background.add(ender)
    ender.add_done_callback(_background.discard)
```

- [ ] **Step 6: Tell her about it in the system prompt**

Add to `SYSTEM_PROMPT`, after the LOOKING THINGS UP section:

```
"VIDEO. You can play a video on your own screen with play_video, and stop it "
"with stop_video. When you play something, the conversation ends immediately "
"so the video can have the screen — say one short sentence about what you are "
"playing and nothing more. If the user asks for something you cannot find, "
"say so instead of playing something else.\n\n"
```

- [ ] **Step 7: Add the configuration**

In `voice-agent/.env.example`:

```
# The robot's Flask app, for playing videos on its screen. The token is
# generated on the robot and stored in its gitignored config.json as
# "video_token" — the two must match.
VIDEO_BASE_URL=http://robot.local:8080
VIDEO_API_TOKEN=
```

Then put the real values in `voice-agent/.env` (never committed) using the token from Task 5.

- [ ] **Step 8: Run the tests and commit**

Run: `make -C voice-agent test`
Expected: PASS

```bash
git add voice-agent/video_control.py voice-agent/tests/test_video_control.py \
        voice-agent/agent.py voice-agent/.env.example
git commit -m "feat(agent): play and stop videos on the robot's screen"
```

---

### Task 10: End-to-end check and documentation

**Files:**
- Modify: `inventory.md`, `README.md`
- Create: `docs/logs/019-2026-09-18-video-playback.md`
- Modify: `docs/logs/README.md`

- [ ] **Step 1: Restart everything and run the full suites**

```bash
ssh <robot> 'systemctl --user restart robot-face wake-word video-player'
make -C voice-agent restart
cd robot-face && python3 -m pytest tests -q
make -C voice-agent test
```

- [ ] **Step 2: Walk the real paths and record what happens**

1. Panel: play a URL with a start time → it appears on the robot's screen at that point.
2. Panel: Pause, Resume, Stop → the face returns on Stop.
3. Panel: play a search phrase → the right video, with its title shown.
4. Say "Gerdoo, baba" while it plays → video stops, face returns, call connects; end the call → the video resumes near where it left off.
5. In a call: "play me X" → she confirms, the call ends, the video starts.
6. Say "گردو بسه" over the video's own audio → it stops. **This is the one the hardware echo cancellation has to earn** — if the wake word cannot hear you over the video, record it as a finding.
7. Unplug nothing, but `systemctl --user stop video-player` and press Play → the panel says the player is unreachable, and the page does not hang.

- [ ] **Step 3: Write log 019**

Follow `docs/logs/README.md`: what changed, the evidence from step 2 with real numbers, wrong turns, and an honest list of what is NOT covered — especially anything from step 2 that failed. Include the `yt-dlp` update command, because that is the thing that will break silently in six months.

- [ ] **Step 4: Update the reference docs**

- `inventory.md`: under Audio or a new Video heading — mpv plus yt-dlp, the unit name, the socket path, the token in `config.json`, and the two `.env` names. Note the 16 kHz audio ceiling here too.
- `docs/logs/README.md`: add the 019 row.
- `README.md`: mention video playback in the component list.

- [ ] **Step 5: Scan for anything personal, then commit and push**

Before every push, read the added lines and check for anything personal. The
patterns are kept out of this file on purpose — writing them down here would
publish the very strings they exist to catch. They are: the owner's name and
surname, the personal domain, the router's local hostname suffix, the robot's
SSH username, the home LAN's address prefix, and any populated API key or
token assignment.

```bash
git add -A
git diff --cached -U0 | grep '^+' | less    # read it; do not push what you have not read
git commit -m "docs: video playback on the robot's screen"
git push origin main
```

The video token must appear in **no** committed file — only in the robot's
`config.json` and `voice-agent/.env`, both gitignored. The same goes for the
robot's hostname: every command in this plan writes `<robot>` for that reason.

---

## Self-review

**Spec coverage:** player service (4), `video.py` with parse/resolve/IPC (1-3), Flask routes and token (5), deferral and pause-for-a-call (5, 6), panel card (7), wake-word stop (8), agent tools and end-of-call (9), error handling (5, 6, and the 503/400 tests), testing (every task), docs and bench checks (4, 8, 10).

**Placeholders:** none — every step carries its code or its exact command. `<robot>` is deliberate: the host is personal and must not be committed.

**Type consistency:** `score()` returns `(action, conf, text)` everywhere after Task 8, and all three call sites are updated in the same task. `video.status()` returns the same five keys in Tasks 2, 5, 6 and 7, with `deferred` added only by the route layer. `video_control.play/stop` return a dict with `ok`, and the tools check `ok` before anything else.

**One risk to watch:** Task 2's fake accepts a single connection per command. If the client is ever changed to reuse a connection, those tests need rewriting — the test file says so at the fixture.
