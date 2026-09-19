"""
Speaker volume on the reSpeaker XVF3800.

There are TWO playback controls on this board, and both cap the output:

  PCM,0   left/right — PulseAudio drives this one to 100% whenever it sets
          sink volume, so it is usually already at 0 dB
  PCM,1   a mono master — ships at 67% = -20 dB and quietly caps everything
          else, which is why the speaker sounded broken until log 018

A volume control that moved only one of them would appear to work and do
nothing, which is exactly what `SPK_LEVEL=85%` did for weeks: PulseAudio kept
PCM,0 at full while only PCM,1 was held back. So setting the volume here writes
BOTH, and reading it reports the quieter of the two — the one that is actually
limiting the sound you hear.

Like video.py and teensy.py, this imports no Flask: all of it is testable
without a sound card.
"""

import re
import subprocess

CARD_MATCH = "XVF3800"
CONTROLS = ("PCM,0", "PCM,1")
TIMEOUT_S = 5


class AudioError(RuntimeError):
    pass


# `/proc/asound/cards` looks like:
#    0 [C16K6Ch        ]: USB-Audio - reSpeaker Flex XVF3800 C16K6Ch
_CARD_LINE = re.compile(r"^\s*(\d+)\s*\[")

# `amixer sget` prints e.g.
#    Mono: Playback 60 [100%] [0.00dB] [on]
#    Front Left: Playback 51 [85%] [-9.00dB] [on]
_PERCENT = re.compile(r"\[(\d{1,3})%\]")


def parse_card_index(text, match=CARD_MATCH):
    """The card number whose description contains `match`, or None.

    Resolved by name on every call, never cached: card indices move on replug,
    the same trap as /dev/ttyACM* and PortAudio indices.
    """
    for line in text.splitlines():
        if match not in line:
            continue
        m = _CARD_LINE.match(line)
        if m:
            return int(m.group(1))
    return None


def parse_percent(text):
    """The lowest percentage in amixer's output, or None if it printed none.

    Lowest, not first: a stereo control prints one per channel, and the
    quietest channel is what the listener hears.
    """
    found = [int(p) for p in _PERCENT.findall(text)]
    return min(found) if found else None


def _run(args):
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=TIMEOUT_S)
    except FileNotFoundError:
        raise AudioError("amixer is not installed")
    except subprocess.TimeoutExpired:
        raise AudioError("amixer did not answer")
    if proc.returncode != 0:
        raise AudioError((proc.stderr or proc.stdout or "amixer failed").strip())
    return proc.stdout


def card_index():
    try:
        with open("/proc/asound/cards") as f:
            text = f.read()
    except OSError as e:
        raise AudioError(f"cannot read sound cards: {e}")
    idx = parse_card_index(text)
    if idx is None:
        raise AudioError(f"no sound card matching {CARD_MATCH!r} — is the board plugged in?")
    return idx


def get_volume():
    """The effective speaker volume, 0-100.

    The quieter of the two controls, because that is the one limiting output.
    """
    card = card_index()
    levels = []
    for control in CONTROLS:
        pct = parse_percent(_run(["amixer", "-c", str(card), "sget", control]))
        if pct is not None:
            levels.append(pct)
    if not levels:
        raise AudioError("amixer reported no volume for either control")
    return min(levels)


def set_volume(percent):
    """Set both playback controls. Returns the volume actually read back."""
    try:
        percent = int(percent)
    except (TypeError, ValueError):
        raise AudioError("volume must be a number")
    percent = max(0, min(100, percent))
    card = card_index()
    for control in CONTROLS:
        _run(["amixer", "-c", str(card), "sset", control, f"{percent}%", "unmute"])
    return get_volume()
