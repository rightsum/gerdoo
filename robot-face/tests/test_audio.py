"""Speaker volume — the parsing, and the rule that both controls move."""

import pytest

import audio


# --- card discovery ---------------------------------------------------------

CARDS = """\
 0 [C16K6Ch        ]: USB-Audio - reSpeaker Flex XVF3800 C16K6Ch
                      Seeed Studio reSpeaker Flex XVF3800 C16K6Ch at usb-3610000.usb-2.3
 1 [Brio           ]: USB-Audio - Brio 500
                      Logitech Brio 500 at usb-3610000.usb-1
"""


def test_finds_the_array_by_name():
    assert audio.parse_card_index(CARDS) == 0


def test_card_index_is_not_assumed_to_be_zero():
    swapped = "\n".join(reversed(CARDS.splitlines()))
    # The array's own line still carries its index, wherever it appears.
    assert audio.parse_card_index(swapped) == 0


def test_missing_board_is_not_a_card():
    assert audio.parse_card_index(" 1 [Brio  ]: USB-Audio - Brio 500") is None


# --- volume parsing ---------------------------------------------------------

def test_reads_a_mono_control():
    assert audio.parse_percent("  Mono: Playback 60 [100%] [0.00dB] [on]") == 100


def test_reports_the_quieter_channel():
    text = ("  Front Left: Playback 60 [100%] [0.00dB] [on]\n"
            "  Front Right: Playback 51 [85%] [-9.00dB] [on]")
    assert audio.parse_percent(text) == 85


def test_no_percentage_at_all():
    assert audio.parse_percent("Simple mixer control 'PCM',0") is None


# --- setting -----------------------------------------------------------------

class FakeAmixer:
    """Records every amixer call and answers sget from a dict."""

    def __init__(self, levels):
        self.levels = dict(levels)
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if "sget" in args:
            control = args[args.index("sget") + 1]
            return f"  Mono: Playback 60 [{self.levels[control]}%] [0.00dB] [on]"
        if "sset" in args:
            control = args[args.index("sset") + 1]
            self.levels[control] = int(args[args.index("sset") + 2].rstrip("%"))
        return ""


@pytest.fixture
def amixer(monkeypatch):
    fake = FakeAmixer({"PCM,0": 100, "PCM,1": 85})
    monkeypatch.setattr(audio, "_run", fake)
    monkeypatch.setattr(audio, "card_index", lambda: 0)
    return fake


def test_the_quieter_control_is_what_gets_reported(amixer):
    # PulseAudio holds PCM,0 at 100 while PCM,1 caps the output at 85.
    assert audio.get_volume() == 85


def test_setting_moves_both_controls(amixer):
    # The bug this guards: writing one control looks like it works and does
    # nothing, because the other one still caps the output.
    assert audio.set_volume(70) == 70
    written = [a for a in amixer.calls if "sset" in a]
    assert {a[a.index("sset") + 1] for a in written} == {"PCM,0", "PCM,1"}


def test_volume_is_clamped_to_the_possible(amixer):
    assert audio.set_volume(500) == 100
    assert audio.set_volume(-20) == 0


def test_a_volume_that_is_not_a_number_is_refused(amixer):
    with pytest.raises(audio.AudioError):
        audio.set_volume("loud")


def test_a_missing_board_says_so(monkeypatch):
    monkeypatch.setattr(audio, "parse_card_index", lambda *a, **k: None)
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))
    with pytest.raises(audio.AudioError):
        audio.card_index()
