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
