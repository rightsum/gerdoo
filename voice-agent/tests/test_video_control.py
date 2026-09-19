import json

import video_control


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = json.dumps(body).encode()
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_play_posts_the_target_and_the_token(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["token"] = req.headers.get("X-video-token")
        seen["body"] = json.loads(req.data)
        return FakeResponse({"ok": True, "title": "Talagh", "deferred": True})

    monkeypatch.setattr(video_control.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(video_control, "BASE_URL", "http://robot:8080")
    monkeypatch.setattr(video_control, "TOKEN", "s3cret")

    out = video_control.play("talagh", start="1:30")
    assert out["title"] == "Talagh"
    assert out["deferred"] is True
    assert seen["url"] == "http://robot:8080/api/video/play"
    assert seen["token"] == "s3cret"
    assert seen["body"] == {"url_or_query": "talagh", "start": "1:30"}


def test_play_reports_an_error_instead_of_raising(monkeypatch):
    def boom(req, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr(video_control.urllib.request, "urlopen", boom)
    # BASE_URL/TOKEN must be set here, or _post short-circuits on the "not
    # configured" branch before ever reaching urlopen, and this test would be
    # asserting the wrong error message.
    monkeypatch.setattr(video_control, "BASE_URL", "http://robot:8080")
    monkeypatch.setattr(video_control, "TOKEN", "s3cret")
    out = video_control.play("talagh")
    assert out["ok"] is False
    assert "connection refused" in out["error"]


def test_play_without_configuration_says_so(monkeypatch):
    monkeypatch.setattr(video_control, "BASE_URL", "")
    out = video_control.play("talagh")
    assert out["ok"] is False
    assert "not configured" in out["error"]


def test_stop_posts_to_the_stop_endpoint(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        return FakeResponse({"ok": True})

    monkeypatch.setattr(video_control.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(video_control, "BASE_URL", "http://robot:8080")
    monkeypatch.setattr(video_control, "TOKEN", "s3cret")
    assert video_control.stop()["ok"] is True
    assert seen["url"] == "http://robot:8080/api/video/stop"
