import time

import jwt
import pytest

import voice

KEY = "devkey"
SECRET = "secret-at-least-32-characters-long-x"


def decode(token):
    return jwt.decode(token, SECRET, algorithms=["HS256"])


def test_token_is_signed_with_the_secret():
    token = voice.mint_token("gerdoo", "face", KEY, SECRET)
    claims = decode(token)
    assert claims["iss"] == KEY
    assert claims["sub"] == "face"


def test_token_grants_join_to_the_named_room():
    claims = decode(voice.mint_token("gerdoo", "face", KEY, SECRET))
    grant = claims["video"]
    assert grant["room"] == "gerdoo"
    assert grant["roomJoin"] is True


def test_token_can_publish_and_subscribe():
    grant = decode(voice.mint_token("gerdoo", "face", KEY, SECRET))["video"]
    assert grant["canPublish"] is True
    assert grant["canSubscribe"] is True


def test_token_expires_in_the_future():
    claims = decode(voice.mint_token("gerdoo", "face", KEY, SECRET, ttl_s=60))
    assert claims["exp"] > time.time()
    assert claims["exp"] <= time.time() + 61


def test_token_is_rejected_by_the_wrong_secret():
    token = voice.mint_token("gerdoo", "face", KEY, SECRET)
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "a-completely-different-secret", algorithms=["HS256"])


@pytest.mark.parametrize("state", [
    "idle", "connecting", "listening", "thinking", "speaking", "error",
])
def test_known_states_are_valid(state):
    assert voice.is_valid_state(state) is True


@pytest.mark.parametrize("state", ["", "connected", "banana", "IDLE", None])
def test_unknown_states_are_rejected(state):
    assert voice.is_valid_state(state) is False


def test_connected_is_deliberately_not_a_state():
    # It would flash past in milliseconds on the way to `listening`; the spec
    # drops it on purpose. This test exists so nobody adds it back by reflex.
    assert "connected" not in voice.VOICE_STATES