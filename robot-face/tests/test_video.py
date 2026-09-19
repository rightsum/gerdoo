import json
import os
import shutil
import socket
import tempfile
import threading

import pytest

import video


# ---- start times ----

def test_plain_seconds():
    assert video.parse_start("90") == 90


def test_minutes_and_seconds():
    assert video.parse_start("1:30") == 90


def test_hours_minutes_seconds():
    assert video.parse_start("1:02:03") == 3723


def test_compact_form():
    assert video.parse_start("1h2m3s") == 3723


def test_blank_is_no_start():
    assert video.parse_start("") is None
    assert video.parse_start(None) is None


def test_junk_is_rejected():
    with pytest.raises(ValueError):
        video.parse_start("half past four")


def test_negative_is_rejected():
    with pytest.raises(ValueError):
        video.parse_start("-5")


def test_start_comes_from_the_url_when_not_given():
    url = "https://www.youtube.com/watch?v=abc123&t=42s"
    assert video.parse_start(None, url=url) == 42


def test_explicit_start_beats_the_url():
    url = "https://www.youtube.com/watch?v=abc123&t=42"
    assert video.parse_start("1:00", url=url) == 60


def test_youtu_be_short_link_start():
    assert video.parse_start(None, url="https://youtu.be/abc123?t=7") == 7


# ---- url vs search ----

def test_watch_url_is_a_url():
    assert video.looks_like_url("https://www.youtube.com/watch?v=abc123")


def test_short_link_is_a_url():
    assert video.looks_like_url("https://youtu.be/abc123")


def test_bare_words_are_a_search():
    assert not video.looks_like_url("googoosh talagh")


def test_a_word_with_a_dot_is_still_a_search():
    assert not video.looks_like_url("mr. bean cartoon")


# ---- mpv IPC client ----

class FakeMpv:
    """A unix socket that answers mpv's JSON IPC, for tests."""

    def __init__(self, sock_dir, replies=None, silent=False):
        self.path = os.path.join(sock_dir, "mpv.sock")
        self.replies = replies or {}
        self.silent = silent
        self.received = []
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.path)
        self.sock.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                buf = b""
                while b"\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        return
                    buf += chunk
                line = buf.split(b"\n", 1)[0]
                req = json.loads(line)
                self.received.append(req)
                if self.silent:
                    return
                name = req["command"][0]
                prop = req["command"][1] if len(req["command"]) > 1 else None
                key = f"{name}:{prop}" if name == "get_property" else name
                # An unrelated event first: the client must skip it.
                conn.sendall(json.dumps({"event": "playback-restart"}).encode() + b"\n")
                body = {"request_id": req.get("request_id", 0)}
                if key in self.replies:
                    body.update({"data": self.replies[key], "error": "success"})
                else:
                    body.update({"error": "property unavailable"})
                conn.sendall(json.dumps(body).encode() + b"\n")

    def close(self):
        self.sock.close()


@pytest.fixture
def fake_mpv(monkeypatch):
    made = []
    # Deliberately not pytest's tmp_path: its default root nests under
    # pytest-of-<user>/pytest-N/<test-name>N/, and that plus "mpv.sock"
    # routinely exceeds macOS's ~104-byte sockaddr_un limit (108 on Linux),
    # so the bind() below fails before the client is ever exercised. /tmp
    # is named explicitly rather than via tempfile's default gettempdir(),
    # because on macOS TMPDIR itself is the long path that causes this.
    sock_dir = tempfile.mkdtemp(dir="/tmp")

    def make(replies=None, silent=False):
        m = FakeMpv(sock_dir, replies=replies, silent=silent)
        monkeypatch.setattr(video, "SOCKET_PATH", m.path)
        made.append(m)
        return m

    yield make
    for m in made:
        m.close()
    shutil.rmtree(sock_dir, ignore_errors=True)


def test_command_returns_the_data(fake_mpv):
    fake_mpv({"get_property:duration": 212.5})
    assert video.command("get_property", "duration") == 212.5


def test_command_skips_events_before_the_reply(fake_mpv):
    m = fake_mpv({"get_property:time-pos": 12.0})
    assert video.command("get_property", "time-pos") == 12.0
    assert m.received[0]["command"] == ["get_property", "time-pos"]


def test_unavailable_property_is_none_not_an_error(fake_mpv):
    fake_mpv({})
    assert video.command("get_property", "time-pos") is None


def test_missing_socket_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(video, "SOCKET_PATH", str(tmp_path / "nope.sock"))
    with pytest.raises(video.VideoError):
        video.command("get_property", "duration")


def test_a_silent_player_raises_rather_than_hanging(fake_mpv, monkeypatch):
    fake_mpv(silent=True)
    monkeypatch.setattr(video, "TIMEOUT_S", 0.3)
    with pytest.raises(video.VideoError):
        video.command("get_property", "duration")


def test_play_sends_loadfile_with_a_start(fake_mpv):
    m = fake_mpv({"loadfile": None})
    video.play_url("https://youtu.be/abc123", start=90)
    assert m.received[0]["command"] == [
        "loadfile", "https://youtu.be/abc123", "replace", "start=90"]


def test_play_without_a_start_sends_no_options(fake_mpv):
    m = fake_mpv({"loadfile": None})
    video.play_url("https://youtu.be/abc123")
    assert m.received[0]["command"] == [
        "loadfile", "https://youtu.be/abc123", "replace"]


def test_status_reports_idle_as_not_playing(fake_mpv):
    fake_mpv({"get_property:idle-active": True})
    st = video.status()
    assert st["playing"] is False
    assert st["title"] is None


def test_status_reports_a_playing_video(fake_mpv):
    fake_mpv({
        "get_property:idle-active": False,
        "get_property:media-title": "Talagh",
        "get_property:time-pos": 31.4,
        "get_property:duration": 212.5,
        "get_property:pause": False,
    })
    st = video.status()
    assert st == {"playing": True, "paused": False, "title": "Talagh",
                  "position": 31, "duration": 212}


def test_pause_and_resume_set_the_property(fake_mpv):
    m = fake_mpv({"set_property": None})
    video.pause()
    video.resume()
    assert m.received[0]["command"] == ["set_property", "pause", True]


def test_stop_sends_stop(fake_mpv):
    m = fake_mpv({"stop": None})
    video.stop()
    assert m.received[0]["command"] == ["stop"]


# ---- resolve ----

def test_resolve_searches_for_bare_words(monkeypatch):
    calls = []

    def fake_run(args, timeout=None):
        calls.append(args)
        return "abc123|Googoosh - Talagh"

    monkeypatch.setattr(video, "_run", fake_run)
    url, title = video.resolve("googoosh talagh")
    assert url == "https://www.youtube.com/watch?v=abc123"
    assert title == "Googoosh - Talagh"
    assert "ytsearch1:googoosh talagh" in calls[0]
    # Only the first result is processed. Without this yt-dlp answers quickly and
    # then keeps running, and the wait for exit times out anyway.
    assert calls[0][calls[0].index("-I") + 1] == "1"


def test_resolve_keeps_a_url_and_fetches_its_title(monkeypatch):
    monkeypatch.setattr(video, "_run", lambda args, timeout=None: "Talagh")
    url, title = video.resolve("https://youtu.be/abc123")
    assert url == "https://youtu.be/abc123"
    assert title == "Talagh"


def test_resolve_plays_a_url_even_if_the_title_lookup_fails(monkeypatch):
    def boom(args, timeout=None):
        raise video.VideoError("yt-dlp failed")

    monkeypatch.setattr(video, "_run", boom)
    url, title = video.resolve("https://youtu.be/abc123")
    assert url == "https://youtu.be/abc123"
    assert title is None


def test_resolve_raises_when_a_search_finds_nothing(monkeypatch):
    monkeypatch.setattr(video, "_run", lambda args, timeout=None: "")
    with pytest.raises(video.VideoError):
        video.resolve("asdkjhasdkjh nonsense query")


def test_resolve_rejects_an_empty_target():
    with pytest.raises(ValueError):
        video.resolve("   ")
