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


# Searching YouTube from the robot is wildly variable: the same query measured
# 4s, then twice ran past two minutes. 25s tripped during a real conversation.
RESOLVE_TIMEOUT_S = 40


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

    # -I 1 is a fix, not an optimisation. Without it yt-dlp printed a usable
    # result within seconds and then kept working for minutes — and subprocess
    # waits for the process to EXIT, so a search that had already answered still
    # hit the timeout and the robot said it could not find anything. Measured on
    # the robot: 3-4s with it; 4s once and twice past two minutes without.
    # --flat-playlist is faster still, but its top hit for a singer's name is the
    # artist's CHANNEL rather than a video, so it cannot be used here.
    out = _run(["--no-playlist", "-I", "1", "--print", "%(id)s|%(title)s",
                f"ytsearch1:{target}"])
    if not out or "|" not in out:
        raise VideoError(f"nothing found for {target!r}")
    video_id, _, title = out.partition("|")
    return f"https://www.youtube.com/watch?v={video_id}", title.strip() or None
