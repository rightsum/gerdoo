"""Gesture detection control and relay for the control panel.

Mirrors lidar.py: this module never imports MediaPipe. The detector runs as a
separate on-demand systemd user unit in its own virtualenv (numpy 2.2 / cv2 5.0
there, against numpy 1.21 / cv2 4.8 here) and pushes results over localhost.
"""
import json
import queue
import subprocess
import threading
import time

UNIT = "gesture.service"

# A detection older than this is stale — detector stopped or camera went off.
STALE_AFTER = 5.0

_lock = threading.Lock()
_sub_lock = threading.Lock()
_subscribers = set()
_latest = None
_latest_at = 0.0
_count = 0


def _systemctl(*args, timeout=15):
    try:
        p = subprocess.run(["systemctl", "--user", *args],
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode == 0, (p.stdout + p.stderr).strip()
    except FileNotFoundError:
        return False, "systemctl not found"
    except subprocess.TimeoutExpired:
        return False, f"systemctl {' '.join(args)} timed out"


def unit_installed():
    ok, out = _systemctl("list-unit-files", UNIT, "--no-legend")
    return ok and UNIT in out


def is_active():
    _, out = _systemctl("is-active", UNIT)
    return out.strip() == "active"


def start():
    if not unit_installed():
        return False, f"{UNIT} is not installed — run ./deploy/deploy.sh"
    ok, out = _systemctl("start", UNIT)
    return ok, out or "started"


def stop():
    global _latest
    ok, out = _systemctl("stop", UNIT)
    with _lock:
        _latest = None
    return ok, out or "stopped"


def ingest(det):
    global _latest, _latest_at, _count
    with _lock:
        _latest = det
        _latest_at = time.time()
        _count += 1
    payload = json.dumps(det)
    with _sub_lock:
        for q in list(_subscribers):
            try:
                q.put_nowait(payload)
            except queue.Full:
                try:
                    q.get_nowait()      # drop oldest, keep the connection
                    q.put_nowait(payload)
                except (queue.Empty, queue.Full):
                    pass


def subscribe():
    q = queue.Queue(maxsize=4)
    with _sub_lock:
        _subscribers.add(q)
    return q


def unsubscribe(q):
    with _sub_lock:
        _subscribers.discard(q)


def latest():
    with _lock:
        if _latest is None or time.time() - _latest_at > STALE_AFTER:
            return None
        return _latest


def status():
    with _lock:
        age = (time.time() - _latest_at) if _latest_at else None
        cur = _latest
        n = _count
    return {
        "unit": UNIT,
        "installed": unit_installed(),
        "active": is_active(),
        "detections": n,
        "last_age": round(age, 2) if age is not None else None,
        "current": cur,
        "viewers": len(_subscribers),
    }
