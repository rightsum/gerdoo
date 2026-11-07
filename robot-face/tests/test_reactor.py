"""The reactor screen: choosing a look, drawing each one, and the /api/reactor routes."""

import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("PIL")

import reactor_screen as R  # noqa: E402


@pytest.fixture
def files(tmp_path, monkeypatch):
    state, battery = tmp_path / "state.json", tmp_path / "battery.json"
    monkeypatch.setattr(R, "STATE_FILE", str(state))
    monkeypatch.setattr(R, "BATTERY_FILE", str(battery))

    def write(voice="idle", reactor=None, ups=(12.3, 91), main=(0.0, 0)):
        s = {"voice": voice}
        if reactor:
            s["reactor"] = reactor
        state.write_text(json.dumps(s))
        battery.write_text(json.dumps({
            "jetson_battery": {"voltage": ups[0], "percent": ups[1]},
            "main_battery": {"voltage": main[0], "percent": main[1]}}))
    return write


@pytest.mark.parametrize("voice,look", [
    ("idle", "idle"), ("connecting", "listening"), ("listening", "listening"),
    ("thinking", "thinking"), ("speaking", "speaking"), ("error", "idle"),
])
def test_the_voice_state_picks_the_look(files, voice, look):
    files(voice=voice)
    assert R.choose() == (look, 91)


def test_an_override_wins_over_the_voice(files):
    files(voice="speaking", reactor="charging")
    assert R.choose()[0] == "charging"
    files(voice="speaking", reactor="auto")
    assert R.choose()[0] == "speaking"


def test_low_battery_shows_low_but_never_during_a_conversation(files):
    files(ups=(10.2, 9))
    assert R.choose() == ("low", 9)
    files(voice="listening", ups=(10.2, 9))
    assert R.choose()[0] == "listening"


def test_an_unwired_main_battery_sensor_is_ignored(files):
    # The Teensy's voltage sensor read 0 V while unwired: that must not mean "empty".
    files(ups=(12.3, 91), main=(0.0, 0))
    assert R.battery_percent() == 91
    files(ups=(12.3, 91), main=(11.4, 40))
    assert R.battery_percent() == 40


def test_missing_files_fall_back_to_idle(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "STATE_FILE", str(tmp_path / "nope.json"))
    monkeypatch.setattr(R, "BATTERY_FILE", str(tmp_path / "nope2.json"))
    assert R.choose() == ("idle", None)


@pytest.mark.parametrize("look", R.LOOKS)
def test_every_look_draws_a_full_valid_frame(look):
    r = R.Reactor()
    for t in (0, .7, 2.6):
        img = r.render(look, t, 12 if look == "low" else 68)
        assert img.shape == (R.H, R.W, 3)
        assert np.isfinite(img).all()
        assert img.min() >= -1e-6 and img.max() <= 1 + 1e-6


def test_only_the_changed_rectangle_is_sent():
    a = np.zeros((R.H, R.W), np.uint16)
    assert R.changed_box(None, a) == (0, 0, R.W - 1, R.H - 1)
    assert R.changed_box(a, a.copy()) is None
    b = a.copy()
    b[10:20, 30:41] = 1
    assert R.changed_box(a, b) == (30, 10, 40, 19)


def test_changed_pixels_go_out_as_few_small_rectangles():
    a = np.zeros((R.H, R.W), np.uint16)
    assert R.changed_rects(a, a.copy()) == []
    assert R.changed_rects(None, a) == [(0, 0, R.W - 1, R.H - 1)]
    b = a.copy()
    b[100:104, 50:55] = 1                        # a small dot: one 8 px tile-aligned square
    assert R.changed_rects(a, b) == [(48, 96, 55, 103)]
    c = a.copy()                                 # a thin frame outline: its sides, not the whole screen
    c[20:22, 20:220] = 1
    c[258:260, 20:220] = 1
    c[20:260, 20:22] = 1
    c[20:260, 218:220] = 1
    rects = R.changed_rects(a, c)
    sent = sum((x1 - x0 + 1) * (y1 - y0 + 1) for x0, y0, x1, y1 in rects)
    assert sent < .25 * R.W * R.H
    assert len(rects) <= R.MAX_RECTS
    covered = np.zeros_like(c, bool)
    for x0, y0, x1, y1 in rects:
        covered[y0:y1 + 1, x0:x1 + 1] = True
    assert covered[c == 1].all()                 # nothing that changed is left out


# --- routes -----------------------------------------------------------------

pytest.importorskip("flask")
import app as robot_app  # noqa: E402


@pytest.fixture
def client(monkeypatch, tmp_path):
    robot_app.app.config["TESTING"] = True
    monkeypatch.setattr(robot_app, "load_config", lambda: {"moods": [], "secret_key": "x"})
    monkeypatch.setattr(robot_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(robot_app, "REACTOR_STATUS_FILE", str(tmp_path / "reactor.json"))
    with robot_app.app.test_client() as c:
        c._tmp = tmp_path
        yield c


def test_setting_and_reading_the_mode(client):
    assert client.get("/api/reactor").get_json()["mode"] == "auto"
    assert client.post("/api/reactor", json={"look": "charging"}).status_code == 200
    assert client.get("/api/reactor").get_json()["mode"] == "charging"
    assert json.loads((client._tmp / "state.json").read_text())["reactor"] == "charging"


def test_an_unknown_look_is_refused(client):
    assert client.post("/api/reactor", json={"look": "disco"}).status_code == 400
    assert client.post("/api/reactor", json={}).status_code == 400


def test_a_stale_status_reads_as_not_running(client):
    import time
    (client._tmp / "reactor.json").write_text(json.dumps({"look": "idle", "updated": time.time() - 60}))
    s = client.get("/api/reactor").get_json()
    assert s["running"] is False and s["look"] is None
    (client._tmp / "reactor.json").write_text(json.dumps({"look": "thinking", "updated": time.time()}))
    s = client.get("/api/reactor").get_json()
    assert s["running"] is True and s["look"] == "thinking"
