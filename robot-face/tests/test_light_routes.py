"""The light: parsing the Teensy's LIGHT line, and the /api/light routes."""

import pytest

import teensy

AUTO = "LIGHT raw=3022 norm=1.000 cal_dark=529 cal_bright=1400 duty=38/4095 (cap of 4095) mode=auto level=-1.00"
MANUAL = "LIGHT raw=900 norm=0.425 cal_dark=529 cal_bright=1400 duty=2048/4095 (cap of 4095) mode=manual level=0.50"


def test_parsing_auto():
    s = teensy.parse_light(AUTO)
    assert s["mode"] == "auto"
    assert s["sensor"] == 1.0 and s["sensor_raw"] == 3022
    assert s["duty"] == 38 and s["duty_max"] == 4095
    assert s["cal_dark"] == 529 and s["cal_bright"] == 1400
    assert s["level"] is None                   # -1 in auto


def test_parsing_manual():
    s = teensy.parse_light(MANUAL)
    assert s["mode"] == "manual"
    assert s["level"] == 0.5


def test_older_firmware_without_level_still_parses():
    s = teensy.parse_light(AUTO.replace(" level=-1.00", ""))
    assert s["mode"] == "auto" and s["level"] is None


def test_a_line_that_is_not_light_is_not_parsed():
    assert teensy.parse_light("HEARTBEAT seq=1 ldr=3022 strip=38") is None
    assert teensy.parse_light(None) is None


# --- routes -----------------------------------------------------------------

pytest.importorskip("flask")
import app as robot_app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    robot_app.app.config["TESTING"] = True
    monkeypatch.setattr(robot_app, "load_config", lambda: {"moods": [], "secret_key": "x"})
    sent = []

    def fake_send(cmd, expect, timeout=1.5):
        sent.append(cmd)
        if cmd == "LIGHT":
            return AUTO
        if cmd == "STRIP auto":
            return "STRIP mode=auto"
        if cmd.startswith("STRIP "):
            return f"STRIP mode=manual level={int(cmd.split()[1]) / 100:.2f}"
        if cmd.startswith("CAL "):
            return f"CAL {cmd.split()[1]}=777"
        raise AssertionError(cmd)

    monkeypatch.setattr(teensy, "send", fake_send)
    with robot_app.app.test_client() as c:
        c._sent = sent
        yield c


def test_reading_the_light(client):
    s = client.get("/api/light").get_json()
    assert s["mode"] == "auto" and s["duty"] == 38
    assert client._sent == ["LIGHT"]


def test_auto_and_fixed_levels(client):
    assert client.post("/api/light", json={"mode": "auto"}).status_code == 200
    assert client.post("/api/light", json={"level": 0}).status_code == 200
    assert client.post("/api/light", json={"level": 100}).status_code == 200
    assert client._sent == ["STRIP auto", "STRIP 0", "STRIP 100"]


@pytest.mark.parametrize("body", [{"level": -1}, {"level": 101}, {"level": "bright"}, {"mode": "on"}, {}])
def test_bad_levels_never_reach_the_teensy(client, body):
    assert client.post("/api/light", json=body).status_code == 400
    assert client._sent == []


def test_calibrating_both_ends(client):
    assert client.post("/api/light/calibrate", json={"which": "dark"}).get_json()["raw"] == 777
    assert client.post("/api/light/calibrate", json={"which": "bright"}).status_code == 200
    assert client.post("/api/light/calibrate", json={"which": "middle"}).status_code == 400
    assert client._sent == ["CAL dark", "CAL bright"]


def test_a_missing_teensy_is_503(client, monkeypatch):
    def gone(*a, **k):
        raise teensy.TeensyError("Teensy not connected")
    monkeypatch.setattr(teensy, "send", gone)
    assert client.get("/api/light").status_code == 503
