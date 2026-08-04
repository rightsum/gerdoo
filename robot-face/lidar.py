"""LiDAR control and scan relay for the control panel.

Two jobs, deliberately separated from ROS:

  1. Start/stop the lidar. It runs as an on-demand systemd *user* unit
     (`rplidar.service`, NOT enabled at boot) so the motor only spins when
     someone asks. This module just shells out to `systemctl --user`.

  2. Relay scans to browsers. The Flask app cannot `import rclpy` — that only
     works with a ROS environment sourced, and coupling the face app to ROS
     would mean it could not start without it. So a separate bridge process
     (scan_bridge.py, launched by the same unit) subscribes to /scan and POSTs
     downsampled frames to /api/lidar/ingest on localhost. This module holds
     the newest frame and fans it out over SSE, reusing the pattern the mood
     broadcaster already uses.
"""
import json
import queue
import subprocess
import threading
import time

UNIT = "rplidar.service"

# A scan older than this is stale — the bridge stopped, or the lidar died.
SCAN_STALE_AFTER = 3.0

_lock = threading.Lock()
_sub_lock = threading.Lock()
_subscribers = set()      # set[queue.Queue]
_latest = None            # last scan dict
_latest_at = 0.0
_scan_count = 0


# --- systemd control -------------------------------------------------------
def _systemctl(*args, timeout=15):
    """Run `systemctl --user ...` and return (ok, output)."""
    try:
        p = subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return p.returncode == 0, (p.stdout + p.stderr).strip()
    except FileNotFoundError:
        return False, "systemctl not found"
    except subprocess.TimeoutExpired:
        return False, f"systemctl {' '.join(args)} timed out"


def unit_installed():
    ok, out = _systemctl("list-unit-files", UNIT, "--no-legend")
    return ok and UNIT in out


def is_active():
    ok, out = _systemctl("is-active", UNIT)
    return out.strip() == "active"


def start():
    if not unit_installed():
        return False, (
            f"{UNIT} is not installed. Deploy it: "
            f"cp deploy/rplidar.service ~/.config/systemd/user/ && "
            f"systemctl --user daemon-reload"
        )
    ok, out = _systemctl("start", UNIT)
    return ok, out or "started"


def stop():
    ok, out = _systemctl("stop", UNIT)
    with _lock:
        globals()["_latest"] = None
    return ok, out or "stopped"


# --- scan relay ------------------------------------------------------------
def ingest(scan):
    """Called by the ROS bridge with a downsampled scan."""
    global _latest, _latest_at, _scan_count
    with _lock:
        _latest = scan
        _latest_at = time.time()
        _scan_count += 1
    payload = json.dumps(scan)
    with _sub_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(payload)
            except queue.Full:
                # Slow client: drop this frame rather than stall the bridge.
                dead.append(q)
        for q in dead:
            try:
                q.get_nowait()      # make room, keep the connection
            except queue.Empty:
                pass


def subscribe():
    # maxsize 2: a viewer that cannot keep up should see the newest scans, not
    # a growing backlog of old ones.
    q = queue.Queue(maxsize=2)
    with _sub_lock:
        _subscribers.add(q)
    return q


def unsubscribe(q):
    with _sub_lock:
        _subscribers.discard(q)


def latest():
    with _lock:
        if _latest is None:
            return None
        if time.time() - _latest_at > SCAN_STALE_AFTER:
            return None
        return _latest


def status():
    with _lock:
        age = (time.time() - _latest_at) if _latest_at else None
        count = _scan_count
    active = is_active()
    return {
        "unit": UNIT,
        "installed": unit_installed(),
        "active": active,
        "scanning": active and age is not None and age <= SCAN_STALE_AFTER,
        "last_scan_age": round(age, 2) if age is not None else None,
        "scans": count,
        "viewers": len(_subscribers),
    }
