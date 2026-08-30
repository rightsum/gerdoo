"""
Decisions about when a voice session ends.

Deliberately free of LiveKit imports and I/O. Session-ending logic is the part
most likely to be wrong and the least pleasant to debug through a live
microphone, so it lives here where it can be tested in milliseconds.
"""

# Matched case-insensitively as substrings of the final transcript. A plain
# substring match rather than an LLM intent call: deterministic, free, and a
# chatty model cannot talk itself out of ending the session.
CLOSING_PHRASES = ("خداحافظ", "khodahafez", "goodbye")


def is_closing_phrase(text: str) -> bool:
    """True if the user's final transcript should end the session."""
    if not text:
        return False
    lowered = text.casefold()
    return any(p.casefold() in lowered for p in CLOSING_PHRASES)


class SilenceTimer:
    """
    Tracks how long it has been since the user last spoke.

    Timed from the end of the last USER utterance, not from the end of the
    agent's reply — what is being waited on is the user, so a long answer from
    the robot must not eat the window.
    """

    def __init__(self, timeout_s: float = 30.0, now: float = 0.0):
        self.timeout_s = timeout_s
        self._last_spoke = now

    def mark_user_spoke(self, now: float) -> None:
        self._last_spoke = now

    def expired(self, now: float) -> bool:
        return (now - self._last_spoke) > self.timeout_s