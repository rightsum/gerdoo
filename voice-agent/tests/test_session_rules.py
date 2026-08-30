import pytest

from session_rules import CLOSING_PHRASES, SilenceTimer, is_closing_phrase


@pytest.mark.parametrize("text", [
    "خداحافظ",
    "khodahafez",
    "Khodahafez",
    "KHODAHAFEZ",
    "goodbye",
    "ok goodbye then",
    "خب خداحافظ",
])
def test_closing_phrases_are_recognised(text):
    assert is_closing_phrase(text) is True


@pytest.mark.parametrize("text", [
    "",
    "   ",
    "hello",
    "سلام",
    "good morning",
    "what is the weather",
])
def test_ordinary_speech_does_not_close(text):
    assert is_closing_phrase(text) is False


def test_closing_phrase_list_is_not_empty():
    assert len(CLOSING_PHRASES) >= 3


def test_silence_timer_is_not_expired_immediately():
    t = SilenceTimer(timeout_s=30.0)
    t.mark_user_spoke(now=1000.0)
    assert t.expired(now=1000.0) is False


def test_silence_timer_is_not_expired_just_before_the_window():
    t = SilenceTimer(timeout_s=30.0)
    t.mark_user_spoke(now=1000.0)
    assert t.expired(now=1029.9) is False


def test_silence_timer_expires_after_the_window():
    t = SilenceTimer(timeout_s=30.0)
    t.mark_user_spoke(now=1000.0)
    assert t.expired(now=1030.1) is True


def test_user_speech_resets_the_window():
    t = SilenceTimer(timeout_s=30.0)
    t.mark_user_spoke(now=1000.0)
    t.mark_user_spoke(now=1025.0)
    assert t.expired(now=1050.0) is False
    assert t.expired(now=1056.0) is True


def test_timer_before_any_speech_uses_construction_time():
    t = SilenceTimer(timeout_s=30.0, now=500.0)
    assert t.expired(now=520.0) is False
    assert t.expired(now=531.0) is True