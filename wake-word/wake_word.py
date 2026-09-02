#!/usr/bin/env python3
"""
Wake-word trigger — listens for the Persian phrase "Gerdoo, baba" (گردو بابا)
and plays a chime when it hears it.

Approach: Vosk offline ASR with the decoder's grammar restricted to the wake
phrase and nothing else. With only "گردو بابا" and "[unk]" available, the
recogniser cannot wander off into acoustically similar Persian words — which is
exactly what free-form decoding did during calibration, where "گردو" lost out to
"کردی" and the model mostly settled on the bare "بابا".

Two things learned from that calibration run, both encoded here:

  * Fire on FINAL results, not partials. Partial hypotheses are unstable and
    triggered mid-sentence on unrelated speech.
  * Gate on the decoder's word confidences. The grammar makes a match easy to
    reach, so confidence is what keeps false accepts down.

Runs entirely offline. No audio leaves the robot; nothing is written to disk
unless --record or --save-hits is passed.

    python3 wake_word.py --list-devices
    python3 wake_word.py --device 24                        # live
    python3 wake_word.py --device 24 --record session.wav   # live + capture
    python3 wake_word.py --replay session.wav --threshold 0.5
    python3 wake_word.py --replay session.wav --sweep
"""

import argparse
import json
import os
import queue
import subprocess
import sys
import time
import urllib.request
import wave
from datetime import datetime

import numpy as np
from scipy.signal import resample_poly
from vosk import Model, KaldiRecognizer, SetLogLevel

DEFAULT_MODEL = os.path.expanduser("~/models/vosk-model-small-fa-0.42")
DEFAULT_SOUND = os.path.expanduser("~/wake-word/sounds/janam.mp3")

WAKE_PHRASE = "گردو بابا"
WAKE_HEAD = "گردو"   # the discriminating half; "بابا" alone is far too common

# Longest utterance still treated as someone calling the robot. Above this it is
# conversation, not a wake word.
MAX_UTTERANCE_TOKENS = 4

# How often to re-read the panel's master switch. Also bounds how long the
# microphone stays open after someone switches voice off.
SWITCH_POLL_S = 2.0

# Two grammars, and the difference matters far more than the confidence threshold.
#
# STRICT is the phrase and "[unk]" only. It maximises recall, but "[unk]" is a
# weak absorber: with nothing else on offer, ordinary speech collapses onto the
# one real phrase available. That is the false-positive mode seen in service.
#
# FILLER adds competing words — deliberately including the near neighbours of
# "گردو" that fell out of the open-mode calibration (کردی, کردم, کرده) plus
# common conversational Persian. Giving the decoder somewhere else to go is what
# suppresses false accepts; a narrower grammar makes them worse, not better.
GRAMMAR_STRICT = json.dumps([WAKE_PHRASE, "[unk]"], ensure_ascii=False)

FILLER_WORDS = [
    # near neighbours of گردو, straight from the calibration transcript
    "کردی", "کردم", "کرده", "کردن", "گرفتم", "برو", "بردار", "درو", "گرم",
    # bare "بابا" — the model emitted this constantly from ordinary speech
    "بابا", "مامان", "آقا", "خانم",
    # common conversational filler
    "الان", "خوبه", "دارم", "داره", "میکنه", "بیا", "چیه", "یه", "که", "این",
    "اون", "هست", "نیست", "خیلی", "چرا", "کجا", "آره", "نه", "باشه", "ممنون",
]
GRAMMAR_FILLER = json.dumps([WAKE_PHRASE] + FILLER_WORDS + ["[unk]"],
                            ensure_ascii=False)

SAMPLE_RATE = 16000     # what the Vosk models expect
# The USB speaker's mic is 48 kHz-only and PortAudio refuses to open it at
# 16 kHz, so capture native and decimate. 48000/16000 = 3 exactly, a clean
# integer decimation. The Brio does both; 48 k keeps one code path.
CAPTURE_RATE = 48000
BLOCK_SECONDS = 0.25


def play(path, wait=False):
    """
    Fire the response sound without blocking the audio loop.

    Dispatched by extension: paplay and aplay handle PCM only, so an mp3 handed
    to them fails silently — which looks exactly like the detector not firing.
    """
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    if path.lower().endswith((".mp3", ".m4a", ".ogg", ".flac")):
        players = (["mpg123", "-q", path], ["ffplay", "-nodisp", "-autoexit", path])
    else:
        players = (["paplay", path], ["aplay", "-q", path])
    for player in players:
        try:
            proc = subprocess.Popen(player, env=env,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            if wait:
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
            return
        except FileNotFoundError:
            continue
    print(f"no player available for {path}", file=sys.stderr)


def start_voice_session(base_url, timeout=5.0):
    """Ask Flask to start a session. Returns True if it accepted."""
    try:
        req = urllib.request.Request(f"{base_url}/api/voice/wake", method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception as e:
        print(f"  voice wake failed: {e}", file=sys.stderr)
        return False


def voice_disabled(base_url, timeout=3.0):
    """True if the panel's master switch is off. Failure is treated as enabled."""
    try:
        with urllib.request.urlopen(f"{base_url}/api/voice/status", timeout=timeout) as r:
            return json.loads(r.read()).get("enabled", True) is False
    except Exception:
        return False


def voice_state(base_url, timeout=3.0):
    """Current voice state, or None if Flask could not be reached."""
    try:
        with urllib.request.urlopen(f"{base_url}/api/voice/status", timeout=timeout) as r:
            return json.loads(r.read()).get("voice", "idle")
    except Exception:
        # None, not "idle". Treating an unreachable Flask as "session over"
        # would resume the detector mid-conversation on a single blip — the
        # exact thing pausing exists to prevent.
        return None


# Absolute cap on a call. Only a runaway session should ever reach this — a
# real conversation is allowed to run as long as it likes, because the detector
# holds the microphone and reclaiming it mid-sentence kills the call.
SESSION_MAX_S = 3600.0

# A session that never gets past "connecting" is wedged: the browser failed to
# join and nobody is talking to anyone. Give up on those quickly, so the robot
# is not left deaf to its own name.
CONNECTING_MAX_S = 45.0

# Silence after the chime before the session starts, so the tail of the sound
# does not reach the microphone as the browser joins.
CHIME_SETTLE_S = 0.4

# A session is only considered over after this many consecutive idle reads.
# One reading is not enough: a transient failure or a race against the browser's
# first state report would resume the detector during a live conversation.
IDLE_READS_TO_END = 3


def wait_for_session_end(base_url, poll_s=1.0, max_s=SESSION_MAX_S):
    """
    Block until the session is over.

    The detector must not listen during a conversation, or it hears the
    conversation and re-triggers on it. Polling rather than a push because this
    is a plain audio loop with no server in it; one request a second costs
    nothing.
    """
    start = time.time()
    idle_runs = 0
    connecting_since = None
    while time.time() - start < max_s:
        state = voice_state(base_url)
        if state == "idle":
            idle_runs += 1
            if idle_runs >= IDLE_READS_TO_END:
                return True
        elif state is not None:
            idle_runs = 0          # a real non-idle state resets the count
            if state == "connecting":
                connecting_since = connecting_since or time.time()
                if time.time() - connecting_since > CONNECTING_MAX_S:
                    print(f"  stuck on 'connecting' for {CONNECTING_MAX_S:.0f}s; "
                          f"giving up and listening again", file=sys.stderr)
                    return False
            else:
                # An actual conversation. However long it runs, do not take the
                # microphone back — that ends the call mid-sentence.
                connecting_since = None
        # state is None (unreachable): hold the count, neither end nor reset
        time.sleep(poll_s)
    print(f"  session ran past the {max_s / 60:.0f}min cap; resuming anyway",
          file=sys.stderr)
    return False


def score(result):
    """
    (matched, mean_confidence, text) for one final Vosk result.

    Vosk reports a per-word confidence in `result`. Averaging over just the wake
    phrase's words — rather than the whole utterance — keeps surrounding speech
    from dragging the score around.
    """
    text = result.get("text", "").strip()

    # The two words must be ADJACENT. Merely containing both somewhere is not
    # enough: under the filler grammar, ordinary conversation produced hits like
    # "بابا نیست اون خانم گردو آقا" and "بابا میکنه الان گردو بابا میکنه گرم
    # خیلی", which contain both words scattered among filler. Roughly a third of
    # all triggers were this. Requiring the actual phrase removes them.
    tokens = text.split()

    # Calling the robot is a SHORT utterance. Continuous conversation that
    # happens to contain the phrase is long — the false positives in the log ran
    # 7 to 15 words ("بابا میکنه الان گردو بابا میکنه گرم خیلی"), while every
    # genuine call was 2 or 3. Length separates them cleanly.
    if len(tokens) > MAX_UTTERANCE_TOKENS:
        return False, 0.0, text

    idx = None
    for i in range(len(tokens) - 1):
        if tokens[i] == WAKE_HEAD and tokens[i + 1] == "بابا":
            idx = i
            break
    if idx is None:
        return False, 0.0, text

    # Score only the two words of the phrase itself, positionally — not every
    # occurrence of either word in the utterance, which let surrounding filler
    # drag the average around.
    words = result.get("result", [])
    if len(words) == len(tokens) and idx + 1 < len(words):
        pair = words[idx:idx + 2]
    else:
        pair = [w for w in words if w.get("word") in (WAKE_HEAD, "بابا")]
    if not pair:
        return True, 1.0, text          # no per-word data; grammar match alone
    conf = sum(w.get("conf", 0.0) for w in pair) / len(pair)
    return True, conf, text


def to_model_rate(raw, decim, gain=1.0):
    """Native-rate int16 bytes -> 16 kHz int16 bytes, with optional gain."""
    if decim == 1 and gain == 1.0:
        return raw
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if decim != 1:
        x = resample_poly(x, 1, decim)
    if gain != 1.0:
        x = x * gain
    return np.clip(x, -32768, 32767).astype(np.int16).tobytes()


def make_recognizer(model, mode):
    if mode == "open":
        rec = KaldiRecognizer(model, SAMPLE_RATE)
    else:
        grammar = GRAMMAR_FILLER if mode == "filler" else GRAMMAR_STRICT
        rec = KaldiRecognizer(model, SAMPLE_RATE, grammar)
    rec.SetWords(True)
    return rec


def run_replay(model, path, args, threshold, quiet=False, gain=None):
    """Feed a recorded wav through the detector. Returns the number of hits."""
    gain = args.gain if gain is None else gain
    rec = make_recognizer(model, args.mode)
    with wave.open(path, "rb") as w:
        assert w.getframerate() == SAMPLE_RATE, f"{path} must be {SAMPLE_RATE} Hz mono"
        hits = 0
        while True:
            data = w.readframes(SAMPLE_RATE // 4)
            if not data:
                break
            data = to_model_rate(data, 1, gain)
            if rec.AcceptWaveform(data):
                matched, conf, text = score(json.loads(rec.Result()))
                if text and not quiet and args.verbose:
                    print(f"    heard: {text}   conf={conf:.2f}")
                if matched and conf >= threshold:
                    hits += 1
                    if not quiet:
                        print(f"    HIT   conf={conf:.2f}   {text}")
        matched, conf, text = score(json.loads(rec.FinalResult()))
        if matched and conf >= threshold:
            hits += 1
            if not quiet:
                print(f"    HIT   conf={conf:.2f}   {text}")
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, default=None,
                    help="input device index (see --list-devices)")
    ap.add_argument("--device-name", default=None,
                    help="select the input by name substring, e.g. 'Brio'. Preferred "
                         "over --device: PortAudio indices move between reboots and "
                         "replugs, exactly like /dev/ttyACM* does")
    ap.add_argument("--capture-rate", type=int, default=CAPTURE_RATE,
                    help="mic capture rate; decimated to 16 kHz for the model")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--sound", default=DEFAULT_SOUND)
    ap.add_argument("--threshold", type=float, default=0.6,
                    help="minimum mean word confidence to accept a match")
    ap.add_argument("--cooldown", type=float, default=2.0,
                    help="seconds to ignore further hits after a trigger")
    ap.add_argument("--record", default=None,
                    help="save the whole session as 16 kHz mono wav, for offline tuning")
    ap.add_argument("--replay", default=None,
                    help="run a recorded wav through the detector instead of the mic")
    ap.add_argument("--gain", type=float, default=1.0,
                    help="linear gain applied before the model. The Brio's hardware "
                         "gain is nearly maxed, so this is the remaining lever for range")
    ap.add_argument("--sweep", action="store_true",
                    help="with --replay: report hit counts across a range of thresholds")
    ap.add_argument("--sweep-gain", action="store_true",
                    help="with --replay: report hit counts across a range of gains")
    ap.add_argument("--save-hits", default=None,
                    help="directory to write the audio of each trigger. This is the "
                         "only way to find out what a false positive actually was")
    ap.add_argument("--log", default=None,
                    help="append triggers to this file. systemd --user journald is "
                         "not persisted on this box, so stdout alone goes nowhere")
    ap.add_argument("--voice-url", default=None,
                    help="base URL of the robot-face Flask app, e.g. "
                         "http://localhost:8080. When set, a trigger starts a "
                         "LiveKit session and the detector pauses until it ends")
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--mode", choices=["strict", "filler", "open"], default="filler",
                    help="decoder grammar. 'filler' adds competing words and is the "
                         "default; 'strict' is phrase-or-unknown and over-fires; "
                         "'open' is unrestricted, for calibration only")
    ap.add_argument("--open", action="store_true", help="shorthand for --mode open")
    ap.add_argument("--sweep-mode", action="store_true",
                    help="with --replay: compare all three grammars on one recording")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.open:
        args.mode = "open"

    if args.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return 0

    SetLogLevel(-1)
    if not os.path.isdir(args.model):
        print(f"model not found: {args.model}", file=sys.stderr)
        return 1
    model = Model(args.model)

    # ---- offline: replay a recording -------------------------------------
    if args.replay:
        if args.sweep:
            print(f"threshold sweep over {args.replay}")
            for t in [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
                print(f"  threshold {t:.1f}  ->  {run_replay(model, args.replay, args, t, quiet=True)} hits")
            return 0
        if args.sweep_mode:
            print(f"grammar comparison over {args.replay} "
                  f"at threshold {args.threshold}, gain {args.gain}")
            for m in ["strict", "filler", "open"]:
                args.mode = m
                n = run_replay(model, args.replay, args, args.threshold, quiet=True)
                print(f"  {m:7s} ->  {n} hits")
            return 0
        if args.sweep_gain:
            print(f"gain sweep over {args.replay} at threshold {args.threshold}")
            for g in [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0]:
                n = run_replay(model, args.replay, args, args.threshold, quiet=True, gain=g)
                print(f"  gain {g:5.1f}x  ->  {n} hits")
            return 0
        n = run_replay(model, args.replay, args, args.threshold)
        print(f"{n} hit(s) at threshold {args.threshold}")
        return 0

    # ---- live -------------------------------------------------------------
    # Imported here rather than at module scope so --replay and --sweep work on
    # a machine with no sound card at all.
    import sounddevice as sd

    if args.device_name:
        match = [i for i, d in enumerate(sd.query_devices())
                 if args.device_name.lower() in d["name"].lower()
                 and d["max_input_channels"] > 0]
        if not match:
            print(f"no input device matching {args.device_name!r}", file=sys.stderr)
            return 1
        args.device = match[0]

    decim = args.capture_rate // SAMPLE_RATE
    if args.capture_rate % SAMPLE_RATE:
        print(f"capture rate must be a multiple of {SAMPLE_RATE}", file=sys.stderr)
        return 1

    rec = make_recognizer(model, args.mode)
    q = queue.Queue()

    def cb(indata, frames, tinfo, status):
        if status:
            print(f"audio status: {status}", file=sys.stderr)
        q.put(bytes(indata))

    dev = sd.query_devices(args.device, "input") if args.device is not None else None
    print(f"listening on: {dev['name'] if dev else 'default'}   "
          f"phrase: {WAKE_PHRASE}   threshold: {args.threshold}", flush=True)

    rectrack = None
    if args.record:
        rectrack = wave.open(args.record, "wb")
        rectrack.setnchannels(1); rectrack.setsampwidth(2); rectrack.setframerate(SAMPLE_RATE)
        print(f"recording to {args.record}", flush=True)

    # 12 blocks x 0.25 s = 3 s of run-up kept, so a saved hit contains whatever
    # was said before the trigger, not just the tail.
    ring, ring_max = [], 12
    last_fire, hits = 0.0, 0
    block = int(args.capture_rate * BLOCK_SECONDS)

    logfh = open(args.log, "a", buffering=1, encoding="utf-8") if args.log else None
    if logfh:
        logfh.write(f"\n=== started {datetime.now():%Y-%m-%d %H:%M:%S} "
                    f"gain={args.gain} threshold={args.threshold} ===\n")

    def open_mic():
        st = sd.RawInputStream(samplerate=args.capture_rate, blocksize=block,
                               dtype="int16", channels=1, device=args.device,
                               callback=cb)
        st.start()
        return st

    def close_mic(st):
        # The Brio is a single hardware capture device and this process holds it
        # through raw ALSA. While it is open, Firefox's getUserMedia succeeds but
        # receives SILENCE — the voice agent then sees the user as "away" and
        # never answers. Releasing it for the duration of a call is the only way
        # both can use the microphone.
        try:
            st.stop()
            st.close()
        except Exception as e:
            print(f"  could not release the mic: {e}", file=sys.stderr)

    stream = open_mic()
    last_switch_check = 0.0
    try:
        if True:
            while True:
                # Master switch. "Off" has to mean the microphone is actually
                # RELEASED, not merely that triggers are ignored — otherwise the
                # Brio's LED stays lit and the robot is still listening, which is
                # not what anyone means by off.
                if args.voice_url and time.time() - last_switch_check >= SWITCH_POLL_S:
                    last_switch_check = time.time()
                    off = voice_disabled(args.voice_url)
                    if off and stream is not None:
                        close_mic(stream)
                        stream = None
                        print("  voice disabled; microphone released", flush=True)
                        if logfh:
                            logfh.write("  voice disabled; microphone released\n")
                    elif not off and stream is None:
                        stream = open_mic()
                        with q.mutex:
                            q.queue.clear()
                        rec.Reset()
                        print("  voice enabled; listening again", flush=True)
                        if logfh:
                            logfh.write("  voice enabled; listening again\n")

                if stream is None:
                    time.sleep(0.5)      # switched off: nothing to decode
                    continue

                data = to_model_rate(q.get(), decim, args.gain)
                if rectrack:
                    rectrack.writeframes(data)
                ring.append(data)
                if len(ring) > ring_max:
                    ring.pop(0)

                # Finals only. Partials fired mid-sentence during calibration.
                if not rec.AcceptWaveform(data):
                    continue
                matched, conf, text = score(json.loads(rec.Result()))
                if text and args.verbose:
                    print(f"  heard: {text}   conf={conf:.2f}", flush=True)
                if not (matched and conf >= args.threshold):
                    continue

                now = time.time()
                if now - last_fire < args.cooldown:
                    continue
                last_fire, hits = now, hits + 1
                stamp = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
                saved = ""
                if args.save_hits:
                    os.makedirs(args.save_hits, exist_ok=True)
                    p = os.path.join(args.save_hits,
                                     datetime.now().strftime("hit-%Y%m%d-%H%M%S.wav"))
                    with wave.open(p, "wb") as w:
                        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
                        w.writeframes(b"".join(ring))
                    saved = f"  audio={p}"
                line = f"[{stamp}] TRIGGER #{hits}  conf={conf:.2f}  {text}{saved}"
                print(line, flush=True)
                if logfh:
                    logfh.write(line + "\n")
                # Master switch. Checked before the chime, so a disabled robot
                # stays completely silent rather than announcing a wake it will
                # not act on.
                if args.voice_url and voice_disabled(args.voice_url):
                    print("  voice disabled in the panel; ignoring", flush=True)
                    if logfh:
                        logfh.write("  voice disabled in the panel; ignoring\n")
                    rec.Reset()
                    last_fire = time.time()
                    continue

                # Wait for the chime to FINISH before handing over to LiveKit.
                # The browser joins with its microphone already live, so a chime
                # still playing out of the speaker becomes the first thing the
                # agent transcribes — it hears itself say "janam" and answers it.
                play(args.sound, wait=bool(args.voice_url))
                if args.voice_url:
                    time.sleep(CHIME_SETTLE_S)   # let the speaker tail decay
                rec.Reset()

                if args.voice_url:
                    already = voice_state(args.voice_url)
                    if already not in (None, "idle"):
                        print(f"  session already active ({already}); not re-triggering",
                              flush=True)
                        if logfh:
                            logfh.write(f"  session already active ({already}); "
                                        f"not re-triggering\n")
                        close_mic(stream)
                        wait_for_session_end(args.voice_url)
                        stream = open_mic()
                        with q.mutex:
                            q.queue.clear()
                        rec.Reset()
                        last_fire = time.time()
                    elif start_voice_session(args.voice_url):
                        print("  session started; mic released, detector paused",
                              flush=True)
                        if logfh:
                            logfh.write("  session started; mic released\n")
                        close_mic(stream)
                        wait_for_session_end(args.voice_url)
                        stream = open_mic()
                        print("  session ended; mic reacquired, listening again",
                              flush=True)
                        if logfh:
                            logfh.write("  session ended; listening again\n")
                        # Audio queued during the conversation is stale and
                        # would be decoded as if it had just been spoken.
                        with q.mutex:
                            q.queue.clear()
                        rec.Reset()
                        last_fire = time.time()
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        if rectrack:
            rectrack.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nstopped")
