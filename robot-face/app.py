#!/usr/bin/env python3
"""
Robot Face — Flask backend.

Serves three things on one port:
  /            the kiosk "face" (opened full-screen by Firefox on the robot)
  /control     a password-protected panel to change the mood (opened from a desktop on the LAN)
  /api/*       state + live event stream that ties the two together

Mood changes made in /control are pushed to every open face over Server-Sent Events,
so the robot's expression updates instantly with no page refresh.
"""
import json
import os
import time
import queue
import threading

from flask import (
    Flask, request, jsonify, Response, render_template,
    redirect, session, url_for,
)
from werkzeug.security import check_password_hash

import gesture
import lidar
from camera import camera, CameraError
import voice


def local_only():
    """True if the request came from this machine.

    The app binds 0.0.0.0, so this is the only thing keeping the internal
    ingest/frame endpoints off the LAN.
    """
    return request.remote_addr in ("127.0.0.1", "::1", "localhost")

BASE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE, "state.json")
CONFIG_FILE = os.path.join(BASE, "config.json")

# --- Moods -----------------------------------------------------------------
# These ids map 1:1 to the <robot-face> component's `emotion` attribute, so a
# mood change is just an attribute swap on the face. "auto" makes the face
# autonomously cycle expressions (a lively default). The canonical list lives
# in config.json ("moods"); this is the first-run fallback.
DEFAULT_MOODS = [
    {"id": "auto",      "label": "Auto",      "emoji": "🔄"},
    {"id": "idle",      "label": "Idle",      "emoji": "😐"},
    {"id": "happy",     "label": "Happy",     "emoji": "😄"},
    {"id": "curious",   "label": "Curious",   "emoji": "🤨"},
    {"id": "love",      "label": "Love",      "emoji": "😍"},
    {"id": "thinking",  "label": "Thinking",  "emoji": "🤔"},
    {"id": "surprised", "label": "Surprised", "emoji": "😮"},
    {"id": "sleepy",    "label": "Sleepy",    "emoji": "😴"},
    {"id": "sad",       "label": "Sad",       "emoji": "😢"},
    {"id": "angry",     "label": "Angry",     "emoji": "😠"},
]

# Curated eye colours offered by the design (Look → color).
DEFAULT_COLORS = ["#FFAE1E", "#FF7A1E", "#FFD34D", "#2AD4FF"]

_state_lock = threading.Lock()
_sub_lock = threading.Lock()
_subscribers = set()  # set[queue.Queue]


# --- Config / state persistence -------------------------------------------
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    else:
        cfg = {}
    cfg.setdefault("moods", DEFAULT_MOODS)
    cfg.setdefault("colors", DEFAULT_COLORS)
    cfg.setdefault("port", 8080)
    # "gl" = WebGL/SDF renderer (falls back to 2D automatically), "2d" = force 2D.
    cfg.setdefault("renderer", "gl")
    # secret_key must be stable so login sessions survive restarts.
    if not cfg.get("secret_key"):
        cfg["secret_key"] = os.urandom(24).hex()
        save_config(cfg)
    return cfg


def save_config(cfg):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def load_state():
    with _state_lock:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"mood": "auto", "color": DEFAULT_COLORS[0], "updated": time.time()}


def save_state(state):
    with _state_lock:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)


# --- Pub/sub for Server-Sent Events ---------------------------------------
def broadcast(payload):
    dead = []
    with _sub_lock:
        for q in _subscribers:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.discard(q)


# --- App -------------------------------------------------------------------
app = Flask(__name__)
_config = load_config()
app.secret_key = _config["secret_key"]
app.permanent_session_lifetime = 60 * 60 * 24 * 30  # 30 days


def mood_ids():
    return {m["id"] for m in load_config()["moods"]}


def logged_in():
    return bool(session.get("auth"))


def password_is_set():
    return bool(load_config().get("password_hash"))


def sensor_guard():
    """Gate for the camera and lidar endpoints.

    Returns a Flask response to abort with, or None to proceed.

    These are held to a HIGHER bar than mood control. With no password the
    panel auto-authenticates every visitor (see /login), which is a tolerable
    default for changing a face — and completely unacceptable for a live
    camera feed of someone's home, or for spinning up hardware. So these
    endpoints require a password to actually EXIST, not merely a session.
    """
    if not logged_in():
        return jsonify(error="unauthorized"), 401
    if not password_is_set():
        return jsonify(
            error="password_required",
            message="Set a control-panel password before enabling the camera or "
                    "lidar: python3 manage.py set-password",
        ), 403
    return None


# ---- Face (public, kiosk) ----
@app.route("/")
def face():
    return render_template("face.html", state=load_state(), renderer=load_config()["renderer"])


@app.route("/api/state")
def api_state():
    return jsonify(load_state())


@app.route("/api/events")
def api_events():
    def stream():
        q = queue.Queue(maxsize=10)
        with _sub_lock:
            _subscribers.add(q)
        try:
            # Prime the connection with the current state.
            yield "data: " + json.dumps(load_state()) + "\n\n"
            while True:
                try:
                    payload = q.get(timeout=20)
                    yield "data: " + json.dumps(payload) + "\n\n"
                except queue.Empty:
                    # Comment line keeps the connection alive through timeouts.
                    yield ": keepalive\n\n"
        finally:
            with _sub_lock:
                _subscribers.discard(q)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---- Voice sessions ----
# The room is fixed: one robot, one conversation. The agent on the Mac is
# auto-dispatched when this room is created, so joining is all the robot does.
VOICE_ROOM = "gerdoo"


def _voice_cfg():
    cfg = load_config()
    return (
        cfg.get("livekit_url", "ws://mac-studio.local:7880"),
        cfg.get("livekit_api_key", "devkey"),
        cfg.get("livekit_api_secret", "secret-at-least-32-characters-long-x"),
    )


def _set_voice(state):
    """Update voice state and push it to the face over the existing SSE."""
    s = load_state()
    s["voice"] = state
    s["updated"] = time.time()
    save_state(s)
    broadcast(s)
    return s


@app.route("/api/voice/wake", methods=["POST"])
def api_voice_wake():
    """Called by the wake-word service. Mints a token and tells the face to join."""
    if not local_only():
        return jsonify(error="forbidden"), 403
    url, key, secret = _voice_cfg()
    token = voice.mint_token(VOICE_ROOM, "face", key, secret)
    _set_voice("connecting")
    return jsonify({"url": url, "token": token, "room": VOICE_ROOM})


@app.route("/api/voice/state", methods=["POST"])
def api_voice_state():
    """Called by the browser as the session progresses."""
    if not local_only():
        return jsonify(error="forbidden"), 403
    data = request.get_json(force=True, silent=True) or {}
    state = data.get("voice")
    if not voice.is_valid_state(state):
        return jsonify({"error": "unknown voice state", "got": state}), 400
    return jsonify(_set_voice(state))


@app.route("/api/voice/status")
def api_voice_status():
    """Polled by the wake-word service so it knows when to resume listening."""
    if not local_only():
        return jsonify(error="forbidden"), 403
    return jsonify({"voice": load_state().get("voice", "idle")})


# ---- Auth ----
@app.route("/login", methods=["GET", "POST"])
def login():
    cfg = load_config()
    if not cfg.get("password_hash"):
        # No password configured yet: control panel is open. Warn in the UI.
        session["auth"] = True
        session.permanent = True
        return redirect(url_for("control"))
    if request.method == "POST":
        pw = request.form.get("password", "")
        if check_password_hash(cfg["password_hash"], pw):
            session["auth"] = True
            session.permanent = True
            return redirect(url_for("control"))
        return render_template("login.html", error="Incorrect password"), 401
    if logged_in():
        return redirect(url_for("control"))
    return render_template("login.html")


@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---- Control panel (auth required) ----
@app.route("/control")
def control():
    if not logged_in():
        return redirect(url_for("login"))
    cfg = load_config()
    return render_template(
        "control.html",
        moods=cfg["moods"],
        colors=cfg["colors"],
        state=load_state(),
        has_password=bool(cfg.get("password_hash")),
        camera_present=camera.status()["present"],
        lidar_installed=lidar.unit_installed(),
        gesture_installed=gesture.unit_installed(),
    )


@app.route("/api/state", methods=["POST"])
def api_set_state():
    """Set the mood and/or eye colour. Body may contain either or both."""
    if not logged_in():
        return jsonify(error="unauthorized"), 401
    data = request.get_json(silent=True) if request.is_json else request.form
    data = data or {}
    cfg = load_config()
    state = load_state()

    if "mood" in data and data["mood"]:
        if data["mood"] not in mood_ids():
            return jsonify(error="unknown mood"), 400
        state["mood"] = data["mood"]
    if "color" in data and data["color"]:
        if data["color"] not in cfg["colors"]:
            return jsonify(error="unknown color"), 400
        state["color"] = data["color"]

    state["updated"] = time.time()
    save_state(state)
    broadcast(state)
    return jsonify(state)


# ---- Camera (auth + password required) ----
@app.route("/api/camera/status")
def api_camera_status():
    guard = sensor_guard()
    if guard:
        return guard
    return jsonify(camera.status())


@app.route("/api/camera/<action>", methods=["POST"])
def api_camera_control(action):
    guard = sensor_guard()
    if guard:
        return guard
    if action == "start":
        try:
            camera.start()
        except CameraError as exc:
            return jsonify(error=str(exc)), 503
    elif action == "stop":
        camera.stop()
    else:
        return jsonify(error="unknown action"), 400
    return jsonify(camera.status())


@app.route("/camera/stream.mjpg")
def camera_stream():
    guard = sensor_guard()
    if guard:
        return guard
    try:
        camera.start()          # idempotent; lets a reload resume the stream
    except CameraError as exc:
        return jsonify(error=str(exc)), 503

    boundary = "frame"

    def generate():
        for jpeg in camera.frames():
            yield (
                b"--" + boundary.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                + jpeg + b"\r\n"
            )

    return Response(
        generate(),
        mimetype=f"multipart/x-mixed-replace; boundary={boundary}",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


# ---- LiDAR (auth + password required) ----
@app.route("/api/lidar/status")
def api_lidar_status():
    guard = sensor_guard()
    if guard:
        return guard
    return jsonify(lidar.status())


@app.route("/api/lidar/<action>", methods=["POST"])
def api_lidar_control(action):
    guard = sensor_guard()
    if guard:
        return guard
    if action == "start":
        ok, out = lidar.start()
    elif action == "stop":
        ok, out = lidar.stop()
    else:
        return jsonify(error="unknown action"), 400
    if not ok:
        return jsonify(error=out), 503
    status = lidar.status()
    status["message"] = out
    return jsonify(status)


@app.route("/api/lidar/ingest", methods=["POST"])
def api_lidar_ingest():
    """Receives scans from scan_bridge.py.

    Localhost only, and no session: the bridge is a local ROS process, not a
    browser.
    """
    if not local_only():
        return jsonify(error="forbidden"), 403
    scan = request.get_json(silent=True)
    if not scan or "ranges" not in scan:
        return jsonify(error="bad scan"), 400
    lidar.ingest(scan)
    return jsonify(ok=True)


@app.route("/api/lidar/stream")
def api_lidar_stream():
    guard = sensor_guard()
    if guard:
        return guard
    q = lidar.subscribe()

    def stream():
        latest = lidar.latest()
        if latest:
            yield "data: " + json.dumps(latest) + "\n\n"
        try:
            while True:
                try:
                    yield "data: " + q.get(timeout=15) + "\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            lidar.unsubscribe(q)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---- Gesture detection (auth + password required) ----
@app.route("/api/camera/frame.jpg")
def api_camera_frame():
    """Single latest frame, for the local gesture detector.

    Localhost only. V4L2 allows one reader and this process owns the camera,
    so the detector cannot open the device itself — it gets frames from here.
    Reading also refreshes the camera's idle timer, so detection keeps the
    camera alive exactly as a browser viewer would.
    """
    if not local_only():
        return jsonify(error="forbidden"), 403
    for frame in camera.frames():          # yields as soon as one is ready
        return Response(frame, mimetype="image/jpeg",
                        headers={"Cache-Control": "no-store"})
    return jsonify(error="camera not running"), 503


@app.route("/api/gesture/status")
def api_gesture_status():
    guard = sensor_guard()
    if guard:
        return guard
    return jsonify(gesture.status())


@app.route("/api/gesture/<action>", methods=["POST"])
def api_gesture_control(action):
    guard = sensor_guard()
    if guard:
        return guard
    if action == "start":
        # Detection is meaningless without frames, so bring the camera up too
        # rather than leaving the detector polling a dead endpoint.
        try:
            camera.start()
        except CameraError as exc:
            return jsonify(error=str(exc)), 503
        ok, out = gesture.start()
    elif action == "stop":
        ok, out = gesture.stop()          # camera left alone; it may be in use
    else:
        return jsonify(error="unknown action"), 400
    if not ok:
        return jsonify(error=out), 503
    status = gesture.status()
    status["message"] = out
    return jsonify(status)


@app.route("/api/gesture/ingest", methods=["POST"])
def api_gesture_ingest():
    if not local_only():
        return jsonify(error="forbidden"), 403
    det = request.get_json(silent=True)
    if det is None or "gesture" not in det:
        return jsonify(error="bad detection"), 400
    gesture.ingest(det)
    return jsonify(ok=True)


@app.route("/api/gesture/stream")
def api_gesture_stream():
    guard = sensor_guard()
    if guard:
        return guard
    q = gesture.subscribe()

    def stream():
        cur = gesture.latest()
        if cur:
            yield "data: " + json.dumps(cur) + "\n\n"
        try:
            while True:
                try:
                    yield "data: " + q.get(timeout=15) + "\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            gesture.unsubscribe(q)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


# ---- Battery ----
BATTERY_FILE = "/tmp/battery_status.json"

@app.route("/api/battery")
def api_battery():
    try:
        with open(BATTERY_FILE) as f:
            return jsonify(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"main_battery": None, "jetson_battery": None})

# ---- Servo (neck pan/tilt) ----
import subprocess as _sp

def _send_teensy(cmd):
    """Send a command to the Teensy console and return its response."""
    try:
        port = "/dev/serial/by-id/usb-Teensyduino_Dual_Serial_19627940-if00"
        p = _sp.Popen(["cat", port], stdout=_sp.PIPE, stderr=_sp.PIPE)
        import time as _t; _t.sleep(0.15)
        _sp.run(["bash", "-c", f"echo {cmd} > {port}"])
        _t.sleep(0.3)
        p.terminate()
        out = p.stdout.read().decode()
        for line in out.strip().split("\n"):
            if "SERVO" in line and "set" in line:
                return line
        return out.strip().split("\n")[-1] if out.strip() else "no response"
    except Exception as e:
        return str(e)

@app.route("/api/servo")
def api_servo_get():
    r = _send_teensy("SERVO")
    # Parse "SERVO set pan=20 tilt=160" or "SERVO current pan=45 tilt=135"
    pan = tilt = None
    for part in r.split():
        if part.startswith("pan="): pan = int(part[4:])
        if part.startswith("tilt="): tilt = int(part[5:])
    return jsonify({"pan": pan, "tilt": tilt, "raw": r})

@app.route("/api/servo", methods=["POST"])
def api_servo_set():
    data = request.get_json(force=True)
    pan = data.get("pan")
    tilt = data.get("tilt")
    cmd_parts = []
    if pan is not None: cmd_parts.append(f"pan={int(pan)}")
    if tilt is not None: cmd_parts.append(f"tilt={int(tilt)}")
    if not cmd_parts:
        return jsonify({"error": "no pan or tilt specified"}), 400
    r = _send_teensy("SERVO " + " ".join(cmd_parts))
    pan = tilt = None
    for part in r.split():
        if part.startswith("pan="): pan = int(part[4:])
        if part.startswith("tilt="): tilt = int(part[5:])
    return jsonify({"pan": pan, "tilt": tilt, "raw": r})


if __name__ == "__main__":
    cfg = load_config()
    app.run(host="0.0.0.0", port=cfg["port"], threaded=True)
