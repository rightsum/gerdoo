"""The /api/cameras/<name>/... routes — the arm cameras on the panel."""

import pytest

# Same reason as test_video_routes: the system Python has no Flask, the
# prepared venv does. Skip rather than error so both runs stay honest.
pytest.importorskip("flask")

import app as robot_app
import camera as camera_mod


class FakeCamera:
    label = "fake camera"

    def __init__(self):
        self.calls = []
        self.running = False

    def start(self):
        self.calls.append("start")
        self.running = True

    def stop(self):
        self.calls.append("stop")
        self.running = False

    def frames(self):
        yield b"\xff\xd8\xff\xe0jpeg"

    def status(self):
        return {"running": self.running, "present": True}


@pytest.fixture
def cams(monkeypatch):
    fakes = {"head": FakeCamera(), "arm_left": FakeCamera(), "arm_right": FakeCamera()}
    monkeypatch.setattr(robot_app, "cameras", fakes)
    monkeypatch.setattr(robot_app, "camera", fakes["head"])
    return fakes


@pytest.fixture
def client(monkeypatch, cams):
    robot_app.app.config["TESTING"] = True
    config = {"moods": [], "secret_key": "x", "password_hash": "set"}
    monkeypatch.setattr(robot_app, "load_config", lambda: dict(config))
    # The test client always looks like 127.0.0.1, which sensor_guard() waves
    # through. These are LAN endpoints; test them as a LAN caller.
    monkeypatch.setattr(robot_app, "local_only", lambda: False)
    with robot_app.app.test_client() as c:
        c._config = config
        yield c


def login(client):
    with client.session_transaction() as s:
        s["auth"] = True


def test_starting_an_arm_camera_starts_only_that_camera(client, cams):
    login(client)
    r = client.post("/api/cameras/arm_left/start")
    assert r.status_code == 200
    assert r.get_json()["running"] is True
    assert cams["arm_left"].calls == ["start"]
    assert cams["arm_right"].calls == [] and cams["head"].calls == []


def test_stopping_an_arm_camera(client, cams):
    login(client)
    client.post("/api/cameras/arm_right/start")
    r = client.post("/api/cameras/arm_right/stop")
    assert r.get_json()["running"] is False


def test_an_unknown_camera_is_404(client):
    login(client)
    assert client.get("/api/cameras/arm_middle/status").status_code == 404
    assert client.post("/api/cameras/arm_middle/start").status_code == 404
    assert client.get("/cameras/arm_middle/stream.mjpg").status_code == 404


def test_an_unknown_action_is_400(client):
    login(client)
    assert client.post("/api/cameras/arm_left/explode").status_code == 400


def test_arm_cameras_need_a_login(client, cams):
    r = client.post("/api/cameras/arm_left/start")
    assert r.status_code == 401
    assert cams["arm_left"].calls == []


def test_arm_cameras_need_a_password_to_exist(client, cams):
    # Same bar as the head camera: a live feed of someone's home is not
    # opened to the LAN on a panel with no password.
    login(client)
    del client._config["password_hash"]
    r = client.post("/api/cameras/arm_left/start")
    assert r.status_code == 403
    assert cams["arm_left"].calls == []


def test_a_camera_that_will_not_open_is_503(client, cams, monkeypatch):
    login(client)

    def boom():
        raise camera_mod.CameraError("Left arm camera not found")
    monkeypatch.setattr(cams["arm_left"], "start", boom)
    r = client.post("/api/cameras/arm_left/start")
    assert r.status_code == 503
    assert "Left arm camera" in r.get_json()["error"]


def test_the_arm_stream_serves_that_cameras_frames(client, cams):
    login(client)
    r = client.get("/cameras/arm_left/stream.mjpg")
    assert r.status_code == 200
    assert r.mimetype == "multipart/x-mixed-replace"
    assert b"jpeg" in r.get_data()
    assert cams["arm_left"].calls == ["start"]


def test_the_old_head_routes_still_drive_the_head_camera(client, cams):
    # The face tracker speaks /api/camera/start; it must keep working.
    login(client)
    r = client.post("/api/camera/start")
    assert r.status_code == 200
    assert cams["head"].calls == ["start"]
    assert cams["arm_left"].calls == []


def test_the_panel_has_a_toggle_for_each_arm_camera(client, monkeypatch):
    monkeypatch.setattr(robot_app, "load_state", lambda: {"mood": "idle"})
    monkeypatch.setattr(robot_app.face_track, "unit_installed", lambda: True)
    monkeypatch.setattr(robot_app.lidar, "unit_installed", lambda: True)
    client._config.update(moods=[], colors=[])
    login(client)
    html = client.get("/control").get_data(as_text=True)
    assert 'data-cam="arm_left"' in html
    assert 'data-cam="arm_right"' in html
