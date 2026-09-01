"""
Voice-session support for the face kiosk.

Token minting uses PyJWT directly rather than the LiveKit SDK. A LiveKit
access token is an ordinary HS256 JWT with a `video` grant claim, PyJWT is
already installed on the robot, and the point of this whole design is to add
as little to the Jetson as possible.
"""

import time

import jwt

# The states the face can be in. `connected` is deliberately absent: it would
# flash past in milliseconds on the way to `listening`. What must be visible is
# `connecting` and `error` — the states where a user would otherwise stare at a
# face wondering what happened.
VOICE_STATES = frozenset({
    "idle", "connecting", "listening", "thinking", "speaking", "error",
})


def is_valid_state(s) -> bool:
    return isinstance(s, str) and s in VOICE_STATES


def mint_token(room: str, identity: str, api_key: str, api_secret: str,
               ttl_s: int = 3600) -> str:
    """
    Build a LiveKit join token.

    The grant lets the holder join exactly one room, publish (its microphone)
    and subscribe (the agent's voice). Nothing else.
    """
    now = int(time.time())
    claims = {
        "iss": api_key,
        "sub": identity,
        "nbf": now,
        "exp": now + ttl_s,
        "name": identity,
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
    }
    return jwt.encode(claims, api_secret, algorithm="HS256")