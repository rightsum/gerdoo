#!/usr/bin/env python3
"""
Point the robot's neck at whoever it is talking to.

Runs only while a voice session is live: the wake word starts a call, this
starts the camera, finds the nearest face and keeps it in the middle of frame,
then stops the camera and re-centres when the call ends.

    face_tracker ── GET  /api/voice/status     is a call happening?
                 ── POST /api/camera/start     only while one is
                 ── GET  /api/camera/frame.jpg
                 ── POST /api/servo            move the neck
                 ── POST /api/camera/stop      when the call ends

Deliberately server-side. The tracking this replaces lived in the control
panel's JavaScript, so the neck only followed anything while somebody happened
to have that page open — the kiosk shows the face, not the panel.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mpp
from mediapipe.tasks.python import vision

import face_tracking as ft

BASE = os.path.dirname(os.path.abspath(__file__))
APP = os.environ.get("ROBOT_FACE_URL", "http://127.0.0.1:8080")
MODEL = os.environ.get(
    "FACE_MODEL", os.path.join(BASE, "models", "blaze_face_short_range.tflite"))

# 4 Hz. Fast enough to follow someone shifting in a chair, slow enough to leave
# the CPU to the voice pipeline — MediaPipe cannot use this board's GPU.
TARGET_HZ = float(os.environ.get("FACE_TRACK_HZ", "4"))

# Minimum detector confidence. Low values invent faces in noise, which is worse
# than missing one: the neck chases nothing.
MIN_CONFIDENCE = 0.5

# Give up on a face after this long and hold position rather than drifting.
FACE_TIMEOUT_S = 2.0

# States that count as "a call is happening".
ACTIVE_VOICE = {"connecting", "listening", "thinking", "speaking"}


LOG_FILE = os.environ.get("FACE_TRACK_LOG",
                          os.path.join(BASE, "face-track.log"))


def log(msg):
    """
    To stdout AND a file. systemd --user journald is not persisted on this
    machine, so stdout alone goes nowhere and a failure leaves no trace — which
    has cost hours before now.
    """
    line = f"{time.strftime('%H:%M:%S')} [face-track] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _get(path, timeout=3.0):
    try:
        with urllib.request.urlopen(f"{APP}{path}", timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def _post(path, payload=None, timeout=5.0):
    data = json.dumps(payload).encode() if payload is not None else b""
    req = urllib.request.Request(
        f"{APP}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception as e:
        log(f"POST {path} failed: {e}")
        return False


def voice_active():
    raw = _get("/api/voice/status")
    if raw is None:
        return False          # cannot ask: assume not, and stay still
    try:
        return json.loads(raw).get("voice") in ACTIVE_VOICE
    except Exception:
        return False


def detect(detector, jpeg):
    """Faces in one frame, normalised. Empty list if none or undecodable."""
    # Half-size decode: the JPEG decoder skips detail rather than producing it
    # and throwing it away. BlazeFace rescales internally anyway.
    arr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_REDUCED_COLOR_2)
    if arr is None:
        return []
    h, w = arr.shape[:2]
    image = mp.Image(image_format=mp.ImageFormat.SRGB,
                     data=cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))
    result = detector.detect(image)

    faces = []
    for d in getattr(result, "detections", []) or []:
        if d.categories and d.categories[0].score < MIN_CONFIDENCE:
            continue
        box = d.bounding_box
        faces.append(ft.Face(
            cx=(box.origin_x + box.width / 2) / w,
            cy=(box.origin_y + box.height / 2) / h,
            w=box.width / w,
            h=box.height / h,
        ))
    return faces


def main():
    if not os.path.exists(MODEL):
        log(f"ERROR: model missing at {MODEL}")
        log("  mkdir -p models && curl -sSL -o models/blaze_face_short_range.tflite \\")
        log("    https://storage.googleapis.com/mediapipe-models/face_detector/"
            "blaze_face_short_range/float16/1/blaze_face_short_range.tflite")
        return 1

    detector = vision.FaceDetector.create_from_options(
        vision.FaceDetectorOptions(
            base_options=mpp.BaseOptions(model_asset_path=MODEL),
            running_mode=vision.RunningMode.IMAGE,
        )
    )
    log(f"ready — following faces during calls, {TARGET_HZ:g} Hz")

    interval = 1.0 / TARGET_HZ
    tracking = False
    pan, tilt = ft.PAN_CENTRE, ft.TILT_CENTRE
    last_seen = 0.0
    no_frame_logged = False
    lost_logged = False

    while True:
        t0 = time.time()
        active = voice_active()

        if active and not tracking:
            tracking = True
            last_seen = 0.0
            lost_logged = False
            log("call started — camera on")
            _post("/api/camera/start")

        elif not active and tracking:
            tracking = False
            log("call ended — camera off, neck centred")
            _post("/api/servo", {"pan": ft.PAN_CENTRE, "tilt": ft.TILT_CENTRE})
            pan, tilt = ft.PAN_CENTRE, ft.TILT_CENTRE
            _post("/api/camera/stop")

        if not tracking:
            time.sleep(0.5)          # idle: cheap poll, no decoding
            continue

        jpeg = _get("/api/camera/frame.jpg")
        if not jpeg:
            if not no_frame_logged:
                log("no frames yet — camera still starting")
                no_frame_logged = True
            time.sleep(0.5)
            continue
        no_frame_logged = False

        face = ft.largest(detect(detector, jpeg))
        if face is None:
            if time.time() - last_seen > FACE_TIMEOUT_S and not lost_logged:
                log("no face in frame — holding position")
                lost_logged = True
        else:
            if lost_logged or last_seen == 0.0:
                log(f"face at ({face.cx:.2f}, {face.cy:.2f})")
            lost_logged = False
            last_seen = time.time()
            if not ft.is_centred(face):
                new_pan, new_tilt = ft.next_position(face, pan, tilt)
                if (round(new_pan), round(new_tilt)) != (round(pan), round(tilt)):
                    pan, tilt = new_pan, new_tilt
                    _post("/api/servo", {"pan": round(pan), "tilt": round(tilt)})

        time.sleep(max(0.0, interval - (time.time() - t0)))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("stopped")
