"""
What the robot listens for, and how a decoder result is judged.

Separate from wake_word.py because that module imports numpy, scipy and vosk at
import time — so none of this could be tested without an audio stack installed.
The matching rules are the part most worth testing: every false positive this
project has had was a bug in here, not in the audio. Standard library only, so
it can be imported and tested on a machine with none of that stack installed.
"""

import json

WAKE_HEAD = "گردو"   # the discriminating half; a bare tail is far too common

# What may follow the head, and what each one asks for. The head is what keeps
# false positives down, so every command shares it — one grammar, one adjacency
# rule, two actions.
WAKE_TAILS = {
    "بابا": "call",     # start a conversation
    "بسه": "stop",      # "enough" — stop the video
    "استاپ": "stop",    # "stop", as commonly borrowed into Persian
}

WAKE_PHRASE = f"{WAKE_HEAD} بابا"   # kept for the startup log line; "the" phrase
WAKE_PHRASES = [f"{WAKE_HEAD} {tail}" for tail in WAKE_TAILS]

# Longest utterance still treated as someone addressing the robot. Above this it
# is conversation, not a command.
MAX_UTTERANCE_TOKENS = 4


def score(result):
    """
    (action, mean_confidence, text) for one final Vosk result.

    `action` is "call", "stop", or None. Confidence is averaged over the two
    words of the phrase only — surrounding filler otherwise drags it around.

    The two words must be ADJACENT. Merely containing both somewhere is not
    enough: under the filler grammar, ordinary conversation produced hits like
    "بابا نیست اون خانم گردو آقا" and "بابا میکنه الان گردو بابا میکنه گرم
    خیلی", which contain both words scattered among filler. Roughly a third of
    all triggers were this. Requiring the actual phrase removes them.
    """
    text = result.get("text", "").strip()
    tokens = text.split()

    # Addressing the robot is a SHORT utterance. Continuous conversation that
    # happens to contain the phrase is long — the false positives in the log ran
    # 7 to 15 words, while every genuine call was 2 or 3. Length separates them
    # cleanly.
    if len(tokens) > MAX_UTTERANCE_TOKENS:
        return None, 0.0, text

    idx, action = None, None
    for i in range(len(tokens) - 1):
        if tokens[i] == WAKE_HEAD and tokens[i + 1] in WAKE_TAILS:
            idx, action = i, WAKE_TAILS[tokens[i + 1]]
            break
    if idx is None:
        return None, 0.0, text

    # Score only the two words of the phrase itself, positionally — not every
    # occurrence of either word in the utterance, which let surrounding filler
    # drag the average around.
    words = result.get("result", [])
    if len(words) == len(tokens) and idx + 1 < len(words):
        pair = words[idx:idx + 2]
    else:
        pair = [w for w in words
                if w.get("word") == WAKE_HEAD or w.get("word") in WAKE_TAILS]
    if not pair:
        return action, 1.0, text        # no per-word data; grammar match alone
    conf = sum(w.get("conf", 0.0) for w in pair) / len(pair)
    return action, conf, text


def grammar(filler_words):
    """
    Vosk decoder grammar: every command phrase, plus competitors.

    FILLER adds competing words — deliberately including the near neighbours of
    "گردو" that fell out of the open-mode calibration (کردی, کردم, کرده) plus
    common conversational Persian. Giving the decoder somewhere else to go is
    what suppresses false accepts; a narrower grammar makes them worse, not
    better. See wake_word.py's FILLER_WORDS for the tuning table itself.
    """
    return json.dumps(WAKE_PHRASES + list(filler_words) + ["[unk]"],
                      ensure_ascii=False)


def strict_grammar():
    """
    STRICT is the phrases and "[unk]" only. It maximises recall, but "[unk]" is
    a weak absorber: with nothing else on offer, ordinary speech collapses onto
    one of the real phrases available. That is the false-positive mode seen in
    service — which is why the live default is the filler grammar, not this one.
    """
    return json.dumps(WAKE_PHRASES + ["[unk]"], ensure_ascii=False)
