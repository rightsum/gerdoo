"""The arms: parsing the Teensy's ARM replies, and the /api/arm/<side> routes."""

import pytest

import teensy

STATE_L = ("ARM L STATE torque=1 speed=400 pos=2075,3111,31,1009,3655,32,3129,2949 "
           "load=0,3,0,12,0,0,0,-1 temp=35,35,35,35,35,35,36,-1")
STATE_R = ("ARM R STATE torque=0 speed=900 pos=1463,3556,2787,2164,58,258,1448,726 "
           "load=0,0,0,0,0,0,0,0 temp=34,32,32,31,31,30,30,28")


def test_parsing_a_state_line():
    s = teensy.parse_arm_state(STATE_L)
    assert s["side"] == "L"
    assert s["torque"] is True
    assert s["pos"] == [2075, 3111, 31, 1009, 3655, 32, 3129, 2949]
    assert s["load"][3] == 12
    assert s["temp"][7] == -1            # a joint that did not answer
    assert s["speed"] == 400


def test_a_line_that_is_not_a_state_is_not_parsed():
    assert teensy.parse_arm_state("HEARTBEAT seq=1 pos=1,2") is None
    assert teensy.parse_arm_state(None) is None


# --- routes -----------------------------------------------------------------

flask = pytest.importorskip("flask")
import app as robot_app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    robot_app.app.config["TESTING"] = True
    config = {"moods": [], "secret_key": "x", "password_hash": "set"}
    monkeypatch.setattr(robot_app, "load_config", lambda: dict(config))
    # The test client looks like 127.0.0.1, which the guard waves through.
    # These endpoints move hardware; test them as a LAN caller.
    monkeypatch.setattr(robot_app, "local_only", lambda: False)
    sent = []

    def fake_send(cmd, expect, timeout=1.5):
        sent.append(cmd)
        _, side, verb, *rest = cmd.split()
        if verb == "STATE":
            return {"L": STATE_L, "R": STATE_R}[side]
        if verb == "TORQUE":
            return f"ARM {side} TORQUE {rest[0].lower()} ok=8"
        if verb == "SPEED":
            return f"ARM {side} SPEED {rest[0]}"
        if verb == "MOVE":
            return f"ARM {side} MOVE joint={rest[0]} goal={rest[1]} ok"
        raise AssertionError(cmd)

    monkeypatch.setattr(teensy, "send", fake_send)
    with robot_app.app.test_client() as c:
        c._config, c._sent = config, sent
        yield c


def login(client):
    with client.session_transaction() as s:
        s["auth"] = True


def test_reading_each_arm(client):
    login(client)
    assert client.get("/api/arm/left").get_json()["pos"][0] == 2075
    assert client.get("/api/arm/right").get_json()["pos"][0] == 1463
    assert client._sent == ["ARM L STATE", "ARM R STATE"]


def test_an_unknown_arm_is_404(client):
    login(client)
    assert client.get("/api/arm/middle").status_code == 404
    assert client.post("/api/arm/middle/move", json={"joint": 1, "pos": 1}).status_code == 404
    assert client._sent == []


def test_enabling_and_releasing_torque(client):
    login(client)
    assert client.post("/api/arm/left/torque", json={"on": True}).status_code == 200
    assert client.post("/api/arm/right/torque", json={"on": False}).status_code == 200
    assert client._sent == ["ARM L TORQUE ON", "ARM R TORQUE OFF"]


def test_moving_a_joint_on_each_arm(client):
    login(client)
    assert client.post("/api/arm/left/move", json={"joint": 3, "pos": 2048}).status_code == 200
    assert client.post("/api/arm/right/move", json={"joint": 8, "pos": 700}).status_code == 200
    assert client._sent == ["ARM L MOVE 3 2048", "ARM R MOVE 8 700"]


@pytest.mark.parametrize("body", [
    {"joint": 0, "pos": 100}, {"joint": 9, "pos": 100},
    {"joint": 3, "pos": -1}, {"joint": 3, "pos": 4096},
    {"joint": "x", "pos": 1}, {"pos": 1}, {},
])
def test_out_of_range_moves_never_reach_the_teensy(client, body):
    login(client)
    assert client.post("/api/arm/left/move", json=body).status_code == 400
    assert client._sent == []


def test_a_refused_move_is_reported_not_swallowed(client, monkeypatch):
    login(client)
    monkeypatch.setattr(teensy, "send", lambda *a, **k: "ARM L MOVE refused: torque is off")
    r = client.post("/api/arm/left/move", json={"joint": 3, "pos": 2048})
    assert r.status_code == 409
    assert "torque is off" in r.get_json()["error"]


def test_setting_the_speed(client):
    login(client)
    r = client.post("/api/arm/right/speed", json={"speed": 1500})
    assert r.status_code == 200
    assert r.get_json()["speed"] == 1500
    assert client._sent == ["ARM R SPEED 1500"]


@pytest.mark.parametrize("body", [{"speed": 10}, {"speed": 5000}, {"speed": "fast"}, {}])
def test_out_of_range_speeds_never_reach_the_teensy(client, body):
    login(client)
    assert client.post("/api/arm/left/speed", json=body).status_code == 400
    assert client._sent == []


def test_the_arms_need_a_password_to_exist(client):
    # They move. Same bar as the cameras: no password, no arms, from the LAN.
    login(client)
    del client._config["password_hash"]
    assert client.post("/api/arm/left/torque", json={"on": True}).status_code == 403
    assert client._sent == []


def test_the_arms_need_a_login(client):
    assert client.post("/api/arm/right/move", json={"joint": 3, "pos": 2048}).status_code == 401
    assert client._sent == []
