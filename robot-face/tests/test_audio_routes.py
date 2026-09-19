"""The /api/audio routes — reading and setting the speaker volume."""

import pytest

# Same reason as test_video_routes: the system Python has no Flask, the
# prepared venv does. Skip rather than error so both runs stay honest.
pytest.importorskip("flask")

import app as robot_app
import audio


@pytest.fixture
def client(monkeypatch):
    robot_app.app.config["TESTING"] = True
    monkeypatch.setattr(robot_app, "load_config",
                        lambda: {"moods": [], "secret_key": "x"})
    with robot_app.app.test_client() as c:
        yield c


def test_reading_the_volume(client, monkeypatch):
    monkeypatch.setattr(audio, "get_volume", lambda: 85)
    r = client.get("/api/audio")
    assert r.status_code == 200
    assert r.get_json()["percent"] == 85


def test_a_missing_board_is_503_not_500(client, monkeypatch):
    def boom():
        raise audio.AudioError("no sound card matching 'XVF3800'")
    monkeypatch.setattr(audio, "get_volume", boom)
    r = client.get("/api/audio")
    assert r.status_code == 503
    assert "XVF3800" in r.get_json()["error"]


def test_setting_the_volume(client, monkeypatch):
    written = []
    monkeypatch.setattr(audio, "set_volume",
                        lambda p: written.append(p) or 70)
    r = client.post("/api/audio", json={"percent": 70})
    assert r.status_code == 200
    assert r.get_json()["percent"] == 70
    assert written == [70]


def test_the_answer_is_what_was_read_back_not_what_was_asked(client, monkeypatch):
    # set_volume clamps; the route must report the truth, not the request.
    monkeypatch.setattr(audio, "set_volume", lambda p: 100)
    r = client.post("/api/audio", json={"percent": 500})
    assert r.get_json()["percent"] == 100


def test_a_request_without_a_percent_is_refused(client):
    r = client.post("/api/audio", json={})
    assert r.status_code == 400


def test_a_volume_that_is_not_a_number_is_503_not_500(client, monkeypatch):
    def boom(p):
        raise audio.AudioError("volume must be a number")
    monkeypatch.setattr(audio, "set_volume", boom)
    r = client.post("/api/audio", json={"percent": "loud"})
    assert r.status_code == 503
