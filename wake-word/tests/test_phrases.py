import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import phrases


def result(text, conf=0.9):
    return {"text": text,
            "result": [{"word": w, "conf": conf} for w in text.split()]}


def test_the_call_phrase_asks_for_a_call():
    action, conf, _ = phrases.score(result("گردو بابا"))
    assert action == "call"
    assert conf == 0.9


def test_the_stop_phrase_asks_for_a_stop():
    action, _, _ = phrases.score(result("گردو بسه"))
    assert action == "stop"


def test_the_english_stop_phrase_also_works():
    action, _, _ = phrases.score(result("گردو استاپ"))
    assert action == "stop"


def test_the_head_word_alone_does_nothing():
    action, _, _ = phrases.score(result("گردو"))
    assert action is None


def test_a_bare_tail_does_nothing():
    action, _, _ = phrases.score(result("بابا"))
    assert action is None


def test_scattered_words_are_rejected():
    action, _, _ = phrases.score(result("بابا نیست گردو آقا"))
    assert action is None


def test_a_long_utterance_is_rejected():
    long_text = "بابا میکنه الان گردو بابا میکنه گرم خیلی"
    action, _, _ = phrases.score(result(long_text))
    assert action is None


def test_a_short_call_with_one_filler_word_still_counts():
    action, _, _ = phrases.score(result("الان گردو بابا"))
    assert action == "call"


def test_confidence_is_averaged_over_the_phrase_only():
    r = {"text": "الان گردو بابا",
         "result": [{"word": "الان", "conf": 0.1},
                    {"word": "گردو", "conf": 0.8},
                    {"word": "بابا", "conf": 1.0}]}
    action, conf, _ = phrases.score(r)
    assert action == "call"
    assert abs(conf - 0.9) < 1e-6
