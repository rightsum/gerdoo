"""The shared camera grabber — frame-rate capping and the camera registry."""

import threading
import time

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

import camera as camera_mod

# Smallest thing _is_jpeg accepts: SOI marker, then anything.
JPEG = np.frombuffer(b"\xff\xd8\xff\xe0" + b"\x00" * 64, dtype=np.uint8)


class FakeCap:
    """Stands in for cv2.VideoCapture: a camera that delivers ~1000 fps."""

    def __init__(self, *args):
        self.settings = {}
        self.grabs = 0
        self.retrieves = 0
        self.released = False

    def isOpened(self):
        return True

    def set(self, prop, value):
        self.settings[prop] = value
        return True

    def get(self, prop):
        # The rate the driver negotiated — what the cap divides down from.
        return 1000.0 if prop == camera_mod.cv2.CAP_PROP_FPS else 0.0

    def grab(self):
        time.sleep(0.001)
        self.grabs += 1
        return True

    def retrieve(self):
        self.retrieves += 1
        return True, JPEG

    def read(self):
        self.grab()
        return self.retrieve()

    def release(self):
        self.released = True


@pytest.fixture
def fake_cap(monkeypatch):
    made = []

    def factory(*args):
        cap = FakeCap(*args)
        made.append(cap)
        return cap

    monkeypatch.setattr(camera_mod.cv2, "VideoCapture", factory)
    monkeypatch.setattr(camera_mod.os.path, "exists", lambda p: True)
    return made


def run_for(cam, seconds):
    cam.start()
    published = []
    deadline = time.time() + seconds

    def consume():
        for frame in cam.frames():
            published.append(frame)
            if time.time() > deadline:
                return

    t = threading.Thread(target=consume, daemon=True)
    t.start()
    t.join(timeout=seconds + 3)
    cam.stop()
    return published


def test_a_capped_camera_publishes_one_frame_in_n(fake_cap):
    # One of the arm cameras cannot be asked for less than 210 fps at
    # 640x400. Passed straight through, that is 20–50 Mbps per viewer on a
    # ~78 Mbps wifi link. Here the driver says 1000 fps and the cap is 10.
    cam = camera_mod.Camera(device="/dev/fake", max_fps=10)
    published = run_for(cam, 1.0)
    cap = fake_cap[0]
    assert cap.grabs > 300
    assert abs(cap.retrieves - cap.grabs // 100) <= 1
    assert len(published) <= cap.retrieves


def test_skipped_frames_are_grabbed_not_retrieved(fake_cap):
    # grab() only dequeues the buffer; retrieve() copies it out. Throwing
    # away 200 frames a second must not pay for 200 copies a second.
    cam = camera_mod.Camera(device="/dev/fake", max_fps=10)
    run_for(cam, 0.5)
    cap = fake_cap[0]
    assert cap.grabs > 50 * cap.retrieves


def test_a_camera_already_at_its_cap_loses_no_frames(fake_cap, monkeypatch):
    # The other arm camera honours a 30 fps request. A clock-based cap would
    # drop every frame that arrived a hair early; this must keep them all.
    monkeypatch.setattr(FakeCap, "get", lambda self, prop: 30.0)
    cam = camera_mod.Camera(device="/dev/fake", fps=30, max_fps=30)
    run_for(cam, 0.3)
    cap = fake_cap[0]
    assert cap.retrieves == cap.grabs


def test_a_capped_camera_gets_a_second_buffer(fake_cap, monkeypatch):
    # With one V4L2 buffer the driver has nowhere to put a frame while that
    # buffer is being handed back. Measured on the 210 fps arm camera: 124
    # frames a second grabbed with one buffer, 211 with two.
    monkeypatch.setattr(FakeCap, "get", lambda self, prop: 210.0)
    cam = camera_mod.Camera(device="/dev/fake", max_fps=30)
    cam.start()
    cam.stop()
    assert fake_cap[0].settings[camera_mod.cv2.CAP_PROP_BUFFERSIZE] == 2


def test_an_uncapped_camera_keeps_one_buffer(fake_cap):
    # The head camera wants the newest frame, never a queued one.
    cam = camera_mod.Camera(device="/dev/fake")
    cam.start()
    cam.stop()
    assert fake_cap[0].settings[camera_mod.cv2.CAP_PROP_BUFFERSIZE] == 1


def test_an_uncapped_camera_publishes_every_frame(fake_cap):
    cam = camera_mod.Camera(device="/dev/fake")
    published = run_for(cam, 0.5)
    assert len(published) > 100


def test_status_reports_the_rate_actually_published(fake_cap, monkeypatch):
    cam = camera_mod.Camera(device="/dev/fake", fps=30, max_fps=15)
    assert cam.status()["fps_target"] == 15      # before start: as asked
    monkeypatch.setattr(FakeCap, "get", lambda self, prop: 210.0)
    cam = camera_mod.Camera(device="/dev/fake", fps=30, max_fps=30)
    cam.start()
    try:
        assert cam.status()["fps_target"] == 30  # 210 / every 7th
    finally:
        cam.stop()


def test_a_missing_camera_names_itself_in_the_error(monkeypatch):
    monkeypatch.setattr(camera_mod.os.path, "exists", lambda p: False)
    cam = camera_mod.Camera(device="/dev/nope", label="Left arm camera")
    with pytest.raises(camera_mod.CameraError, match="Left arm camera"):
        cam.start()


def test_the_head_camera_is_the_one_the_old_routes_use():
    assert camera_mod.cameras["head"] is camera_mod.camera


def test_both_arm_cameras_are_registered_by_usb_port():
    # Both arm cameras report the same serial (SN0001), so /dev/v4l/by-id/
    # holds only one link for the pair. The port path is the only stable
    # name that tells them apart.
    for name in ("arm_left", "arm_right"):
        assert "/dev/v4l/by-path/" in camera_mod.cameras[name].device
    assert camera_mod.cameras["arm_left"].device != camera_mod.cameras["arm_right"].device
