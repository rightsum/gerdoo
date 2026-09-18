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
