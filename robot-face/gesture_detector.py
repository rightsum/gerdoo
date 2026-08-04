#!/usr/bin/env python3
"""Fist / hand-gesture detection for the control panel.

Runs as its OWN process in its OWN virtualenv (~/gesture-venv), because
MediaPipe drags in numpy 2.2 and opencv 5.0 — versions that would break the
system cv2 4.8.0 and ROS Humble. Nothing here is importable from the Flask app
and that is deliberate.

It also cannot open the camera. V4L2 allows exactly one reader, and the Flask
app owns the device so it can serve the video stream. So frames come from the
app over localhost instead:

    robot-face (owns camera, passthrough MJPEG)
        │  GET /api/camera/frame.jpg      (localhost-only)
        ▼
    gesture_detector  ── MediaPipe GestureRecognizer
        │  POST /api/gesture/ingest       (localhost-only)
        ▼
    robot-face ── SSE ──► control panel

Same shape as scan_bridge.py, for the same reason: keep the heavy/awkward
dependency out of the always-on app, and let it crash without taking the face
down.

MediaPipe's canned recogniser classifies: Closed_Fist, Open_Palm, Pointing_Up,
Thumb_Up, Thumb_Down, Victory, ILoveYou, None. "Closed_Fist" is the one asked
for; the rest come free and are reported too.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mpp
from mediapipe.tasks.python import vision

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("GESTURE_MODEL", os.path.join(BASE, "models", "gesture_recognizer.task"))
FRAME_URL = os.environ.get("FRAME_URL", "http://127.0.0.1:8080/api/camera/frame.jpg")
INGEST_URL = os.environ.get("GESTURE_INGEST", "http://127.0.0.1:8080/api/gesture/ingest")

# Measured on a REAL camera frame (not a blank one — a blank image skips the
# landmark stage entirely and reads ~65 ms, which is misleading):
#
#   1280x720  119.7 ms/frame    640x360  116.8 ms/frame
#
# Resolution barely matters because MediaPipe rescales internally; the cost is
# inference, and it is CPU-bound. The prebuilt aarch64 wheel is compiled
# without GPU support ("GPU processing is disabled in build flags"), so the
# Jetson's 1024 CUDA cores cannot be used here at all. Getting onto the GPU
# needs either MediaPipe built from source with GPU flags, or the model
# converted to TensorRT — see logs/010.
#
# 4 Hz is deliberate: a human cannot change gesture meaningfully faster, and it
# keeps this to roughly half a core out of six.
TARGET_HZ = float(os.environ.get("GESTURE_HZ", "4"))

# Below this the recogniser's own guess is not worth reporting.
MIN_SCORE = float(os.environ.get("GESTURE_MIN_SCORE", "0.55"))

# A gesture must persist this many consecutive frames before it is announced.
# Raw per-frame output flickers — a hand mid-close reads as Closed_Fist for a
# frame or two. At 4 Hz, 2 frames is ~0.5 s: still responsive, far steadier.
STABLE_FRAMES = int(os.environ.get("GESTURE_STABLE_FRAMES", "2"))


def log(msg):
    print(f"[gesture] {msg}", flush=True)


def fetch_frame():
    """Latest JPEG from the Flask app, or None if the camera is off."""
    try:
        with urllib.request.urlopen(FRAME_URL, timeout=2.0) as r:
            if r.status != 200:
                return None
            return r.read()
    except (urllib.error.URLError, OSError):
        return None


def push(payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        INGEST_URL, data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=1.5):
            return True
    except (urllib.error.URLError, OSError):
        return False


def main():
    if not os.path.exists(MODEL):
        log(f"ERROR: model missing at {MODEL}")
        log("  curl -sSL -o models/gesture_recognizer.task \\")
        log("    https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
            "gesture_recognizer/float16/1/gesture_recognizer.task")
        return 1

    recognizer = vision.GestureRecognizer.create_from_options(
        vision.GestureRecognizerOptions(
            base_options=mpp.BaseOptions(model_asset_path=MODEL),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,
        )
    )
    log(f"recogniser ready — polling {FRAME_URL} at {TARGET_HZ} Hz")

    interval = 1.0 / TARGET_HZ
    candidate, streak, announced = None, 0, None
    no_frame_logged = False
    frames = 0
    t_report = time.time()

    while True:
        t0 = time.time()

        jpeg = fetch_frame()
        if jpeg is None:
            if not no_frame_logged:
                log("no frames — camera off or app restarting; waiting")
                no_frame_logged = True
            if announced is not None:
                announced = None
                push({"gesture": None, "score": 0.0, "hand": None,
                      "stamp": time.time(), "reason": "camera_off"})
            time.sleep(1.0)
            continue
        no_frame_logged = False

        # IMREAD_REDUCED_COLOR_2 decodes straight to half size — the JPEG
        # decoder skips detail rather than producing it and throwing it away.
        # MediaPipe rescales internally regardless, so 640x360 loses nothing
        # for hand detection and roughly halves the decode cost, which was the
        # single largest slice of this process's CPU.
        arr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_REDUCED_COLOR_2)
        if arr is None:
            continue
        frames += 1

        # MediaPipe wants RGB; OpenCV decodes BGR.
        image = mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))
        result = recognizer.recognize(image)

        name, score, handedness = None, 0.0, None
        if result.gestures and result.gestures[0]:
            top = result.gestures[0][0]
            if top.score >= MIN_SCORE and top.category_name != "None":
                name, score = top.category_name, float(top.score)
                if result.handedness and result.handedness[0]:
                    handedness = result.handedness[0][0].category_name

        # --- position -------------------------------------------------------
        # The recogniser already computes 21 landmarks per hand to classify the
        # gesture; reading them costs nothing extra. This is what turns "is
        # there a fist" into "where is the fist", which is what a neck-tracking
        # loop actually needs.
        #
        # Coordinates are normalised 0..1 in image space, so they stay valid if
        # the camera resolution changes. Origin is top-left.
        pos = None
        if result.hand_landmarks and result.hand_landmarks[0]:
            lm = result.hand_landmarks[0]
            xs = [p.x for p in lm]
            ys = [p.y for p in lm]
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
            # Bounding-box diagonal is a usable proxy for distance: a hand
            # twice as close is roughly twice as large in frame.
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            pos = {
                "x": round(cx, 4),
                "y": round(cy, 4),
                # Error from frame centre — exactly the term a pan/tilt
                # controller wants. Positive x = hand is right of centre.
                "err_x": round(cx - 0.5, 4),
                "err_y": round(cy - 0.5, 4),
                "size": round((w * w + h * h) ** 0.5, 4),
                # Landmark 0 is the wrist — steadier than the centroid when
                # fingers move, which matters if you track through a gesture.
                "wrist_x": round(lm[0].x, 4),
                "wrist_y": round(lm[0].y, 4),
            }

        # Debounce the CLASSIFICATION only. Position is published every frame:
        # a tracking loop needs the newest position even while the gesture
        # label is still settling, and debouncing coordinates would just add
        # lag to the control loop.
        if name == candidate:
            streak += 1
        else:
            candidate, streak = name, 1

        if streak >= STABLE_FRAMES and candidate != announced:
            announced = candidate
            log(f"{announced or 'none'}"
                + (f"  score={score:.2f} hand={handedness}" if announced else ""))

        # Push whenever there is a hand to report, or when the gesture label
        # changed (including to none). Silence when there is nothing at all.
        if pos is not None or candidate != announced or announced is not None:
            push({
                "gesture": announced,
                "is_fist": announced == "Closed_Fist",
                "score": round(score, 3),
                "hand": handedness,
                "pos": pos,
                "stamp": time.time(),
            })

        if time.time() - t_report > 60:
            log(f"{frames} frames in the last 60s")
            frames, t_report = 0, time.time()

        # Hold the target rate; if inference overran, go straight round again.
        time.sleep(max(0.0, interval - (time.time() - t0)))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
