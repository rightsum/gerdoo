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
