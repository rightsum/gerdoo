"""
Face-tracking service control for the panel.

Mirrors lidar.py: this module never imports MediaPipe. The tracker runs as its
own systemd user unit in a separate virtualenv and drives the neck directly, so
there is nothing to relay — the panel only needs to start it, stop it, and say
whether it is running.
"""

import subprocess

UNIT = "face-track.service"


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
    ok, out = _systemctl("is-active", UNIT)
    return out.strip() == "active"


def start():
    return _systemctl("start", UNIT)


def stop():
    return _systemctl("stop", UNIT)


def status():
    return {
        "unit": UNIT,
        "installed": unit_installed(),
        "active": is_active(),
    }
