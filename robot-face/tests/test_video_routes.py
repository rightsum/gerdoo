import json

import pytest

# This machine's system Python has no Flask; the prepared venv does. Skip
# collection here instead of erroring, so the bare `python3 -m pytest tests`
# stays green while the venv run actually exercises these routes.
pytest.importorskip("flask")

import app as robot_app
import video


@pytest.fixture
def client(monkeypatch, tmp_path):
    robot_app.app.config["TESTING"] = True
    state = {"video_pending": None, "voice": "idle"}
    config = {"video_token": "s3cret", "moods": [], "secret_key": "x"}
    monkeypatch.setattr(robot_app, "load_state", lambda: dict(state))
    monkeypatch.setattr(robot_app, "save_state", lambda s: state.update(s))
    monkeypatch.setattr(robot_app, "load_config", lambda: dict(config))
    monkeypatch.setattr(robot_app, "broadcast", lambda payload: None)
    # Flask's test client always reports REMOTE_ADDR as 127.0.0.1, which would
    # let local_only() wave every request through and silently defeat the
    # point of these tests: the video agent genuinely runs on another
    # machine, so token enforcement has to be exercised as a non-local caller.
    monkeypatch.setattr(robot_app, "local_only", lambda: False)
    monkeypatch.setattr(video, "resolve",
                        lambda target: ("https://youtu.be/abc123", "Talagh"))
    monkeypatch.setattr(video, "play_url", lambda url, start=None: None)
    monkeypatch.setattr(video, "stop", lambda: None)
    monkeypatch.setattr(video, "status", lambda: {
        "playing": False, "paused": False, "title": None,
        "position": None, "duration": None})
    with robot_app.app.test_client() as c:
        c._state = state
        yield c


def hdr(token="s3cret"):
    return {"X-Video-Token": token, "Content-Type": "application/json"}


def test_play_requires_a_token(client):
    r = client.post("/api/video/play", json={"url_or_query": "x"})
    assert r.status_code == 403


def test_play_rejects_a_wrong_token(client):
    r = client.post("/api/video/play", json={"url_or_query": "x"},
                    headers=hdr("nope"))
    assert r.status_code == 403


def test_play_rejects_a_non_ascii_token(client):
    # hmac.compare_digest raises TypeError on a non-ASCII str; the guard
    # must deny cleanly (403), not 500.
    r = client.post("/api/video/play", json={"url_or_query": "x"},
                    headers=hdr("نه"))
    assert r.status_code == 403


def test_the_localhost_arm_lets_a_local_caller_in_with_no_token(client, monkeypatch):
    # One of video_guard()'s three documented ways in: a request from this
    # machine itself, with no token and no session at all.
    monkeypatch.setattr(robot_app, "local_only", lambda: True)
    r = client.post("/api/video/stop")
    assert r.status_code == 200


def test_the_session_arm_lets_a_logged_in_caller_in_with_no_token(client):
    # The other documented way in: a logged-in control-panel session, from a
    # non-local address, with no token.
    with client.session_transaction() as s:
        s["auth"] = True
    r = client.post("/api/video/stop")
    assert r.status_code == 200


def test_play_starts_a_video(client):
    r = client.post("/api/video/play",
                    data=json.dumps({"url_or_query": "talagh"}), headers=hdr())
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["title"] == "Talagh"
    assert body["deferred"] is False


def test_play_during_a_call_is_deferred(client):
    client._state["voice"] = "listening"
    r = client.post("/api/video/play",
                    data=json.dumps({"url_or_query": "talagh"}), headers=hdr())
    assert r.get_json()["deferred"] is True
    assert client._state["video_pending"]["url"] == "https://youtu.be/abc123"


def test_a_second_play_replaces_the_pending_one(client, monkeypatch):
    client._state["voice"] = "listening"
    client.post("/api/video/play", data=json.dumps({"url_or_query": "one"}),
                headers=hdr())
    monkeypatch.setattr(video, "resolve",
                        lambda target: ("https://youtu.be/second", "Second"))
    client.post("/api/video/play", data=json.dumps({"url_or_query": "two"}),
                headers=hdr())
    assert client._state["video_pending"]["url"] == "https://youtu.be/second"


def test_play_rejects_a_bad_start_time(client):
    r = client.post("/api/video/play",
                    data=json.dumps({"url_or_query": "x", "start": "half four"}),
                    headers=hdr())
    assert r.status_code == 400


def test_play_reports_a_resolve_failure(client, monkeypatch):
    def boom(target):
        raise video.VideoError("nothing found")

    monkeypatch.setattr(video, "resolve", boom)
    r = client.post("/api/video/play", data=json.dumps({"url_or_query": "zzz"}),
                    headers=hdr())
    assert r.status_code == 400
    assert "nothing found" in r.get_json()["error"]


def test_a_dead_player_is_a_503(client, monkeypatch):
    def boom(url, start=None):
        raise video.VideoError("player not running")

    monkeypatch.setattr(video, "play_url", boom)
    r = client.post("/api/video/play", data=json.dumps({"url_or_query": "x"}),
                    headers=hdr())
    assert r.status_code == 503


def test_stop_clears_a_pending_video(client):
    client._state["video_pending"] = {"url": "u", "title": "t", "start": 5}
    r = client.post("/api/video/stop", headers=hdr())
    assert r.status_code == 200
    assert client._state["video_pending"] is None


def test_status_includes_deferred(client):
    client._state["video_pending"] = {"url": "u", "title": "t", "start": 0}
    r = client.get("/api/video/status", headers=hdr())
    assert r.get_json()["deferred"] is True


def test_a_call_stops_a_playing_video_and_remembers_where(client, monkeypatch):
    stopped = []
    monkeypatch.setattr(video, "status", lambda: {
        "playing": True, "paused": False, "title": "Talagh",
        "position": 42, "duration": 200})
    monkeypatch.setattr(video, "stop", lambda: stopped.append(True))
    monkeypatch.setattr(robot_app, "_current_url", lambda: "https://youtu.be/abc123")

    robot_app._set_voice("connecting")

    assert stopped == [True]
    assert client._state["video_pending"] == {
        "url": "https://youtu.be/abc123", "title": "Talagh", "start": 42}


def test_the_call_ending_resumes_the_video(client, monkeypatch):
    played = []
    client._state["voice"] = "listening"
    client._state["video_pending"] = {
        "url": "https://youtu.be/abc123", "title": "Talagh", "start": 42}
    monkeypatch.setattr(video, "play_url",
                        lambda url, start=None: played.append((url, start)))

    robot_app._set_voice("idle")

    assert played == [("https://youtu.be/abc123", 42)]
    assert client._state["video_pending"] is None


def test_nothing_playing_means_nothing_to_remember(client, monkeypatch):
    # No path means nothing was ever loaded — the yield decision, so nothing
    # further should even be read from status().
    monkeypatch.setattr(robot_app, "_current_url", lambda: None)
    robot_app._set_voice("connecting")
    assert client._state["video_pending"] is None


def test_a_loading_video_is_still_yielded_to_a_call(client, monkeypatch):
    # `playing` is false for seconds after play_url() while mpv's ytdl_hook
    # re-resolves the URL; `path` is set as soon as loadfile is accepted.
    # Keying the yield off status()["playing"] let a video that was still
    # loading survive into a live call and pop up fullscreen mid-conversation.
    stopped = []
    monkeypatch.setattr(video, "status", lambda: {
        "playing": False, "paused": False, "title": None,
        "position": None, "duration": None})
    monkeypatch.setattr(video, "stop", lambda: stopped.append(True))
    monkeypatch.setattr(robot_app, "_current_url",
                        lambda: "https://youtu.be/abc123")

    robot_app._set_voice("connecting")

    assert stopped == [True]
    assert client._state["video_pending"] == {
        "url": "https://youtu.be/abc123", "title": None, "start": 0}


def test_a_loading_video_falls_back_to_the_recorded_start(client, monkeypatch):
    # Position is unavailable while still resolving; do not invent one when
    # there is already a start time on file for this video.
    client._state["video_pending"] = {
        "url": "https://youtu.be/abc123", "title": "Talagh", "start": 42}
    monkeypatch.setattr(video, "status", lambda: {
        "playing": False, "paused": False, "title": None,
        "position": None, "duration": None})
    monkeypatch.setattr(video, "stop", lambda: None)
    monkeypatch.setattr(robot_app, "_current_url",
                        lambda: "https://youtu.be/abc123")

    robot_app._set_voice("connecting")

    assert client._state["video_pending"]["start"] == 42


def test_a_dead_player_does_not_break_a_call(client, monkeypatch):
    def boom():
        raise video.VideoError("player not running")

    monkeypatch.setattr(robot_app, "_current_url", boom)
    robot_app._set_voice("connecting")          # must not raise
    assert client._state["voice"] == "connecting"


def test_a_failed_resume_does_not_break_a_call_or_stay_pending(client, monkeypatch):
    client._state["voice"] = "listening"
    client._state["video_pending"] = {
        "url": "https://youtu.be/abc123", "title": "Talagh", "start": 42}

    def boom(url, start=None):
        raise video.VideoError("player not running")

    monkeypatch.setattr(video, "play_url", boom)
    robot_app._set_voice("idle")                # must not raise
    assert client._state["voice"] == "idle"
    assert client._state["video_pending"] is None
