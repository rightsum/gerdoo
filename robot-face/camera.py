"""Shared USB camera capture for the control panel.

One process, one handle per camera. V4L2 will not let two readers open the same
device, so a single background grabber thread owns the capture and every HTTP
viewer is served the latest frame from memory. That also means N viewers cost
the same as one.

The camera is OFF by default and only runs while explicitly enabled. It also
releases itself once nobody has read a frame for IDLE_TIMEOUT seconds, so a
closed browser tab does not leave a webcam running in someone's home.
"""
import math
import os
import threading
import time

import cv2

# Stable path — keyed on the camera's own serial. /dev/video0 moves when other
# video devices appear, and the Brio claims two nodes (index1 is metadata,
# not capture).
DEFAULT_DEVICE = "/dev/v4l/by-id/usb-046d_Brio_500_2437ZBD0PNK8-video-index0"

# The camera already produces MJPEG and the browser wants MJPEG, so frames are
# passed through untouched — no decode, no re-encode. Measured on this Jetson:
#
#   decode+encode  720p   15.0 fps   40.5% CPU
#   decode+encode 1080p   24.9 fps   89.3% CPU
#   passthrough    720p   25.0 fps    0.5% CPU
#   passthrough   1080p   25.0 fps    0.6% CPU
#
# ~150x cheaper, higher frame rate, and no generation loss from re-encoding.
#
# With CPU no longer the limit, the constraint moved to the NETWORK:
#
#    720p  ~2.6 MB/s  = ~21 Mbps per viewer
#   1080p  ~5.6 MB/s  = ~45 Mbps per viewer
#
# The Jetson's wifi is 2.4 GHz and measured ~78 Mbit/s rx, so 1080p would eat
# most of the link and degrade everything else on it. 720p30 is the default for
# that reason alone — not CPU. Once wifi moves to 5 GHz,
# 1080p becomes reasonable:
#
#   ROBOT_CAMERA_WIDTH=1920 ROBOT_CAMERA_HEIGHT=1080
#
# The camera tops out at ~25 fps in MJPEG at both resolutions regardless of the
# 30 requested — that is the Brio, not this code.
DEFAULT_WIDTH = int(os.environ.get("ROBOT_CAMERA_WIDTH", "1280"))
DEFAULT_HEIGHT = int(os.environ.get("ROBOT_CAMERA_HEIGHT", "720"))
DEFAULT_FPS = int(os.environ.get("ROBOT_CAMERA_FPS", "30"))

# The arm cameras (OV9281 global shutter, one on each gripper). Both report
# the same serial number, SN0001, so /dev/v4l/by-id/ holds ONE link for the
# pair — whichever enumerated last. The USB port path is the only stable name
# that tells them apart, which means each camera must stay in its own port
# on the hub. Swap these two if the panel shows left and right reversed.
ARM_LEFT_DEVICE = os.environ.get(
    "ROBOT_ARM_CAMERA_LEFT",
    "/dev/v4l/by-path/platform-3610000.usb-usb-0:2.1.2:1.0-video-index0")
ARM_RIGHT_DEVICE = os.environ.get(
    "ROBOT_ARM_CAMERA_RIGHT",
    "/dev/v4l/by-path/platform-3610000.usb-usb-0:2.1.3:1.0-video-index0")

# 640x400, not 720p. All three cameras share one USB 2.0 bus, and UVC
# reserves isochronous bandwidth when a stream opens. Measured on this
# Jetson: with both arms at 720p, whichever camera opens third fails with
# "No space left on device". At 640x400 all three run together in any
# order. This is the step-down planned in logs/002.
ARM_WIDTH, ARM_HEIGHT = 640, 400

# Some of these modules ship with firmware that offers only the maximum rate —
# 210 fps at 640x400, nothing lower — and then a request for 30 is ignored.
# The left camera arrived that way, and was reflashed with the right camera's
# firmware (logs/027); both now honour 30. The cap stays as a guard: with
# max-only firmware the grabber publishes every Nth frame instead. Frames here measured 12–30 KB, so 210 fps passed
# straight through is 20–50 Mbps per viewer against ~78 Mbps of wifi; capped
# at 30 it is 3–7 Mbps.
ARM_MAX_FPS = 30

# Only used if passthrough is unavailable and frames must be re-encoded.
JPEG_QUALITY = 80

# Auto-release if no viewer has taken a frame in this long.
IDLE_TIMEOUT = 30.0


class CameraError(RuntimeError):
    pass


class Camera:
    def __init__(self, device=None, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, fps=DEFAULT_FPS,
                 max_fps=None, label="camera"):
        self.device = device or os.environ.get("ROBOT_CAMERA_DEVICE", DEFAULT_DEVICE)
        self.width, self.height, self.fps = width, height, fps
        # Frames beyond this rate are grabbed and dropped, never published.
        self.max_fps = max_fps
        self.label = label
        self._every = 1             # publish every Nth frame, set on start
        self._delivered_fps = fps   # what the driver negotiated, set on start

        self._lock = threading.Lock()
        self._cap = None
        self._thread = None
        self._running = False
        self._frame = None          # latest encoded JPEG bytes
        self._frame_at = 0.0
        self._last_read = 0.0       # when a viewer last took a frame
        self._frames = 0
        self._error = None
        self._mode = None           # "passthrough" or "encode", set by the grabber
        self._bytes = 0
        self._new_frame = threading.Condition(self._lock)

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        with self._lock:
            if self._running:
                return
            if not os.path.exists(self.device):
                raise CameraError(
                    f"{self.label} not found at {self.device} — is it plugged in? "
                    f"(check: ls /dev/v4l/by-id/ /dev/v4l/by-path/)"
                )
            cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap.release()
                raise CameraError(
                    f"could not open {self.label} at {self.device} — another process "
                    f"may hold it, or this user is not in the 'video' group"
                )
            # Ask the camera for MJPEG. Without this V4L2 negotiates raw YUYV,
            # which at 720p is ~27 MB/s over USB and caps the frame rate hard.
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            # Smallest buffer we can ask for: the panel wants the newest frame,
            # not a backlog of stale ones.
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # Hand back the camera's own MJPEG bytes instead of decoding to
            # BGR. This is what makes passthrough possible.
            cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)

            # Cap by counting frames, not by the clock. A clock cap drops any
            # frame that arrives a hair early, so a camera delivering exactly
            # the cap loses every other frame to USB jitter. The rate the
            # driver actually negotiated says how many to skip.
            self._delivered_fps = cap.get(cv2.CAP_PROP_FPS) or self.fps
            if self.max_fps:
                self._every = max(1, math.ceil(self._delivered_fps / self.max_fps - 1e-6))
            else:
                self._every = 1
            # A camera running faster than it is published needs a second
            # buffer. With one, the driver has nowhere to put a frame while
            # that buffer is being handed back — measured on the 210 fps arm
            # camera: 124 fps grabbed with one buffer, 211 with two. The
            # extra frame of latency is 5 ms at that rate.
            if self._every > 1:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

            self._cap = cap
            self._running = True
            self._error = None
            self._frames = 0
            self._last_read = time.time()
            self._thread = threading.Thread(target=self._grab_loop, daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False
            self._new_frame.notify_all()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=3)
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            self._frame = None
            self._thread = None

    # -- grabber -----------------------------------------------------------
    @staticmethod
    def _is_jpeg(buf):
        # A complete JPEG starts FF D8 FF and ends FF D9. V4L2 MJPEG frames are
        # whole JPEGs, so they can go straight to the browser.
        return len(buf) > 4 and buf[0] == 0xFF and buf[1] == 0xD8 and buf[2] == 0xFF

    def _grab_loop(self):
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        every, grabbed = self._every, 0
        consecutive_failures = 0
        while True:
            with self._lock:
                if not self._running:
                    break
                cap = self._cap
                idle = time.time() - self._last_read
            if cap is None:
                break

            # Nobody is watching — shut down rather than keep a camera live.
            if idle > IDLE_TIMEOUT:
                with self._lock:
                    self._running = False
                    self._error = None
                break

            # grab() only dequeues the driver's buffer; retrieve() copies it
            # out. Splitting them lets a frame over the rate cap be dropped
            # without paying for the copy — and the buffer must still be
            # dequeued, or the next read hands back a stale frame.
            ok = cap.grab()
            if ok:
                grabbed += 1
                if grabbed % every:
                    continue
                ok, frame = cap.retrieve()
            if not ok:
                consecutive_failures += 1
                if consecutive_failures >= 30:
                    with self._lock:
                        self._error = "camera stopped delivering frames (unplugged?)"
                        self._running = False
                    break
                time.sleep(0.05)
                continue
            consecutive_failures = 0

            raw = frame.tobytes()
            if self._is_jpeg(raw):
                # Passthrough — the camera's own JPEG, untouched.
                jpeg = raw
                mode = "passthrough"
            else:
                # CONVERT_RGB=0 was ignored (older OpenCV, or a camera with no
                # MJPEG mode), so we got a decoded BGR array and have to encode
                # it. Correct, just far more expensive.
                ok, buf = cv2.imencode(".jpg", frame, encode_params)
                if not ok:
                    continue
                jpeg = buf.tobytes()
                mode = "encode"

            with self._lock:
                self._mode = mode
                self._frame = jpeg
                self._frame_at = time.time()
                self._frames += 1
                # Rough per-second byte rate, for the status line.
                self._bytes = len(jpeg) * self._published_fps()
                self._new_frame.notify_all()

        # Released here so the device is free the moment the loop exits, even
        # on the idle/error paths that did not come through stop().
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            self._running = False
            self._new_frame.notify_all()

    # -- consumers ---------------------------------------------------------
    def frames(self):
        """Yield JPEG bytes as they arrive. Ends when the camera stops."""
        last_at = 0.0
        while True:
            with self._lock:
                if not self._running and self._frame is None:
                    return
                # Wait for a frame newer than the one we already sent, so a
                # slow viewer never re-sends the same image.
                if self._frame is None or self._frame_at <= last_at:
                    self._new_frame.wait(timeout=2.0)
                    if not self._running and self._frame is None:
                        return
                    if self._frame is None or self._frame_at <= last_at:
                        continue
                frame, last_at = self._frame, self._frame_at
                self._last_read = time.time()
            yield frame

    def _published_fps(self):
        # Before the first start the negotiated rate is unknown; assume the
        # requested one.
        if self._every > 1:
            return round(self._delivered_fps / self._every)
        return min(self.fps, self.max_fps) if self.max_fps else self.fps

    def status(self):
        with self._lock:
            return {
                "running": self._running,
                "label": self.label,
                "device": self.device,
                "resolution": f"{self.width}x{self.height}",
                "fps_target": self._published_fps(),
                "frames": self._frames,
                "mode": self._mode,
                "kbps": round(self._bytes * 8 / 1024) if self._bytes else None,
                "error": self._error,
                "present": os.path.exists(self.device),
            }


camera = Camera(label="head camera")

cameras = {
    # The Brio, behind the robot's face. Kept as `camera` too: the face
    # tracker and the original /api/camera/ routes speak to it by that name.
    "head": camera,
    "arm_left": Camera(ARM_LEFT_DEVICE, ARM_WIDTH, ARM_HEIGHT, fps=ARM_MAX_FPS,
                       max_fps=ARM_MAX_FPS, label="left arm camera"),
    "arm_right": Camera(ARM_RIGHT_DEVICE, ARM_WIDTH, ARM_HEIGHT, fps=ARM_MAX_FPS,
                        max_fps=ARM_MAX_FPS, label="right arm camera"),
}
