"""The wheels and ultrasonic sensors: parsing the Teensy's DRIVE line, and the /api/drive routes."""

import pytest

import teensy

DRIVE = "DRIVE run=0,1 duty=0,-15 enc=-395,351 sonar=12.8,-1,-2,-3"


def test_parsing_a_drive_line():
    s = teensy.parse_drive_state(DRIVE)
    assert s["motors"]["L"] == {"running": False, "duty": 0, "enc": -395}
    assert s["motors"]["R"] == {"running": True, "duty": -15, "enc": 351}
    assert s["sonar"]["FL"] == {"state": "ok", "cm": 12.8}
    assert s["sonar"]["FR"] == {"state": "far", "cm": None}       # nothing within range
    assert s["sonar"]["BL"] == {"state": "silent", "cm": None}    # no echo pulse at all
    assert s["sonar"]["BR"] == {"state": "waiting", "cm": None}   # not read since boot


def test_a_line_that_is_not_a_drive_line_is_not_parsed():
    assert teensy.parse_drive_state("HEARTBEAT seq=1 enc=1,2") is None
    assert teensy.parse_drive_state("ENC L=1 R=2") is None
    assert teensy.parse_drive_state(None) is None


# --- routes -----------------------------------------------------------------

flask = pytest.importorskip("flask")
import app as robot_app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    robot_app.app.config["TESTING"] = True
    config = {"moods": [], "secret_key": "x", "password_hash": "set"}
    monkeypatch.setattr(robot_app, "load_config", lambda: dict(config))
    # The wheels move: test as a LAN caller, not the localhost the guard waves through.
    monkeypatch.setattr(robot_app, "local_only", lambda: False)
    sent = []

    def fake_send(cmd, expect, timeout=1.5):
        sent.append(cmd)
        if cmd == "DRIVE":
            return DRIVE
        if cmd == "MOTOR STOP":
            return "MOTOR stopped"
        if cmd.startswith("MOTOR "):
            _, side, pct, ms = cmd.split()
            return f"MOTOR {side} start percent={pct} ms={ms}"
        if cmd == "ENC ZERO":
            return "ENC L=0 R=0"
        raise AssertionError(cmd)

    monkeypatch.setattr(teensy, "send", fake_send)
    with robot_app.app.test_client() as c:
        c._config, c._sent = config, sent
        yield c


def login(client):
    with client.session_transaction() as s:
        s["auth"] = True


def test_reading_the_state(client):
    login(client)
    s = client.get("/api/drive").get_json()
    assert s["motors"]["R"]["enc"] == 351
    assert s["sonar"]["FL"]["cm"] == 12.8
    assert client._sent == ["DRIVE"]


def test_a_timed_run_on_each_side(client):
    login(client)
    assert client.post("/api/drive/run", json={"side": "L", "percent": 15, "ms": 1000}).status_code == 200
    assert client.post("/api/drive/run", json={"side": "R", "percent": -20, "ms": 500}).status_code == 200
    assert client._sent == ["MOTOR L 15 1000", "MOTOR R -20 500"]


@pytest.mark.parametrize("body", [
    {"side": "L", "percent": 0, "ms": 1000},      # not a run
    {"side": "L", "percent": 31, "ms": 1000},     # over the test cap
    {"side": "R", "percent": -31, "ms": 1000},
    {"side": "L", "percent": 15, "ms": 3001},     # too long
    {"side": "L", "percent": 15, "ms": 50},
    {"side": "X", "percent": 15, "ms": 1000},
    {"side": "L", "percent": "fast", "ms": 1000},
    {"percent": 15, "ms": 1000}, {},
])
def test_out_of_range_runs_never_reach_the_teensy(client, body):
    login(client)
    assert client.post("/api/drive/run", json=body).status_code == 400
    assert client._sent == []


def test_a_refused_run_is_reported_not_swallowed(client, monkeypatch):
    login(client)
    monkeypatch.setattr(teensy, "send", lambda *a, **k: "MOTOR ERR range: percent -30..30 (not 0), ms 1..3000")
    r = client.post("/api/drive/run", json={"side": "L", "percent": 15, "ms": 1000})
    assert r.status_code == 409
    assert "MOTOR ERR" in r.get_json()["error"]


def test_stop_and_zero(client):
    login(client)
    assert client.post("/api/drive/stop").status_code == 200
    assert client.post("/api/drive/zero").status_code == 200
    assert client._sent == ["MOTOR STOP", "ENC ZERO"]


def test_the_wheels_need_a_login(client):
    assert client.get("/api/drive").status_code == 401
    assert client.post("/api/drive/run", json={"side": "L", "percent": 15, "ms": 1000}).status_code == 401
    assert client._sent == []


def test_the_wheels_need_a_password_to_exist(client):
    login(client)
    client._config.pop("password_hash")
    assert client.post("/api/drive/run", json={"side": "L", "percent": 15, "ms": 1000}).status_code == 403
    assert client._sent == []
