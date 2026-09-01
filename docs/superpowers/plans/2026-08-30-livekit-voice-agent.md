# LiveKit Voice Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Saying "Gerdoo, baba" to the robot starts a spoken conversation, with speech recognition, the language model and speech synthesis all running on the Mac.

**Architecture:** A `livekit-server` and a `livekit-agents` worker run on the Mac. The Jetson's existing face kiosk browser joins the LiveKit room using the JS SDK — which is what gives us echo cancellation for free, since the robot's speaker sits beside its microphone. The existing Flask app mints the join token and carries voice state over the SSE channel it already has. The existing Vosk wake-word service becomes the trigger and pauses itself for the duration of a session.

**Tech Stack:** `livekit-server` (Homebrew), `livekit-agents` 1.7.1 + `livekit-plugins-elevenlabs` / `-silero` / `-turn-detector`, ElevenLabs STT+TTS, LiteLLM proxy (`glm-5.3:cloud`), Flask 3.1.3, PyJWT 2.3.0, LiveKit JS SDK, Vosk.

**Spec:** [`docs/superpowers/specs/2026-08-30-livekit-voice-agent-design.md`](../specs/2026-08-30-livekit-voice-agent-design.md)

## Global Constraints

- **`livekit-server` must bind `::`**, not the IPv4 default. `mac-studio.local` resolves to AAAA records only — there is no A record.
- **The Jetson gets no new Python dependencies.** PyJWT 2.3.0, Flask 3.1.3 and requests 2.25.1 are already installed; tokens are minted with PyJWT directly rather than by installing the LiveKit SDK on the robot.
- **ElevenLabs and LiteLLM keys never leave the Mac.** Only the LiveKit API key/secret is shared, because Flask must sign tokens with it.
- **`getUserMedia` needs a secure context.** The kiosk loads `http://localhost:8080/`, and localhost qualifies. The same page over plain HTTP from another machine silently gets no microphone.
- **The wake-word service must pause while a session is live**, or it listens to the conversation and re-triggers on it.
- **Session end is decided by the agent**, never by the wake-word service, which is paused and cannot hear the closing phrase.
- Closing phrase: case-insensitive substring match on the **final** STT transcript against `خداحافظ`, `khodahafez`, `goodbye`.
- Silence timeout: **30 s measured from the end of the last user utterance**, not from the end of the agent's reply.
- Real `.env` files are gitignored. Only `.env.example` is committed.

## File Structure

**New — `voice-agent/` (runs on the Mac):**

| File | Responsibility |
|---|---|
| `session_rules.py` | Pure decision logic: does this transcript end the session, has the silence window expired. No I/O, no LiveKit imports — this is the part worth unit-testing |
| `agent.py` | The `livekit-agents` worker. Wires STT → LLM → TTS and applies `session_rules` |
| `livekit.yaml` | Server config, including the `::` bind |
| `.env.example` | Key names, no values |
| `README.md` | How to run both processes |
| `tests/test_session_rules.py` | Unit tests for the pure logic |

**Modified — Jetson:**

| File | Change |
|---|---|
| `robot-face/voice.py` | **New.** Token minting and voice-state helpers. Separate module so `app.py` does not grow another responsibility, and so the logic is testable without a running server |
| `robot-face/app.py` | Three new routes that delegate to `voice.py` |
| `robot-face/templates/face.html` | LiveKit JS client |
| `robot-face/tests/test_voice.py` | **New.** Unit tests for `voice.py` |
| `wake-word/wake_word.py` | Trigger POSTs to Flask; pause and resume around a session |

---

### Task 1: LiveKit server on the Mac

Gets a server running and proves a room can be joined, before any agent code exists.

**Files:**
- Create: `voice-agent/livekit.yaml`
- Create: `voice-agent/.env.example`
- Create: `voice-agent/.gitignore`

**Interfaces:**
- Consumes: nothing
- Produces: a server at `ws://mac-studio.local:7880`, and the key/secret pair from `livekit.yaml` used by every later task

- [ ] **Step 1: Write the server config**

Create `voice-agent/livekit.yaml`:

```yaml
# Binding to :: is required, not cosmetic. mac-studio.local
# resolves to AAAA records only, so an IPv4-only listener is unreachable
# from the Jetson by name.
port: 7880
bind_addresses:
  - "::"

rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 50100
  use_external_ip: false

# Development keys. This server is LAN-only and never exposed to the
# internet. If that changes, these must be replaced.
keys:
  yourkey: <your-api-secret>

logging:
  level: info
```

- [ ] **Step 2: Write the env example and gitignore**

Create `voice-agent/.env.example`:

```bash
# LiveKit — shared with the Jetson's Flask app, which signs join tokens.
LIVEKIT_URL=ws://mac-studio.local:7880
LIVEKIT_API_KEY=<your-api-key>
LIVEKIT_API_SECRET=<your-api-secret>

# ElevenLabs — STT and TTS. Never leaves the Mac.
ELEVEN_API_KEY=

# LiteLLM proxy — OpenAI-compatible. Never leaves the Mac.
LITELLM_BASE_URL=https://litellm.example.com/v1
LITELLM_API_KEY=
LITELLM_MODEL=glm-5.3:cloud
```

Create `voice-agent/.gitignore`:

```
.env
__pycache__/
*.pyc
```

- [ ] **Step 3: Start the server**

Run: `livekit-server --config voice-agent/livekit.yaml`
Expected: log lines including `starting LiveKit server` and `listening on` with port 7880. Leave it running in its own terminal.

- [ ] **Step 4: Verify a room can be created and joined**

In a second terminal:

```bash
export LIVEKIT_URL=ws://localhost:7880
export LIVEKIT_API_KEY=<your-api-key>
export LIVEKIT_API_SECRET=<your-api-secret>
lk room create gerdoo
lk room list
```

Expected: `gerdoo` appears in the list.

- [ ] **Step 5: Verify the Jetson can reach it over IPv6**

```bash
ssh user@<robot-ip> \
  'curl -sS -o /dev/null -w "%{http_code}\n" http://mac-studio.local:7880'
```

Expected: `200`. A connection error means the `::` bind did not take, or the Mac's firewall is blocking 7880.

- [ ] **Step 6: Commit**

```bash
git add voice-agent/livekit.yaml voice-agent/.env.example voice-agent/.gitignore
git commit -m "feat(voice): livekit server config, bound to :: for the IPv6-only hostname"
```

---

### Task 2: Session rules (pure logic, TDD)

The decisions about ending a session, isolated from LiveKit so they can be tested in milliseconds.

**Files:**
- Create: `voice-agent/session_rules.py`
- Test: `voice-agent/tests/test_session_rules.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `is_closing_phrase(text: str) -> bool`
  - `SilenceTimer(timeout_s: float = 30.0)` with `.mark_user_spoke(now: float) -> None`, `.expired(now: float) -> bool`, and attribute `.timeout_s`
  - `CLOSING_PHRASES: tuple[str, ...]`

- [ ] **Step 1: Write the failing tests**

Create `voice-agent/tests/test_session_rules.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd voice-agent && python3 -m pytest tests/test_session_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'session_rules'`

- [ ] **Step 3: Write the implementation**

Create `voice-agent/session_rules.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd voice-agent && python3 -m pytest tests/test_session_rules.py -v`
Expected: PASS, 19 passed

- [ ] **Step 5: Commit**

```bash
git add voice-agent/session_rules.py voice-agent/tests/test_session_rules.py
git commit -m "feat(voice): session-end rules — closing phrase and silence timer"
```

---

### Task 3: The agent worker

Wires STT, the LLM and TTS together and applies the rules from Task 2.

**Files:**
- Create: `voice-agent/agent.py`
- Create: `voice-agent/README.md`

**Interfaces:**
- Consumes: `session_rules.is_closing_phrase`, `session_rules.SilenceTimer`; the env names from Task 1's `.env.example`
- Produces: a worker that auto-joins any room and speaks. Room name `gerdoo` by convention — Task 4 mints tokens for the same name.

- [ ] **Step 1: Write the agent**

Create `voice-agent/agent.py`:

```python
"""
Gerdoo's voice agent. Runs on the Mac, never on the Jetson — the whole point
of this split is to leave the robot's compute for vision and control.

Registers as a livekit-agents worker, so LiveKit dispatches it automatically
when the room is created. That means the robot only has to join a room; no
cross-machine RPC is needed to start a conversation.
"""

import logging
import os
import time

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import elevenlabs, openai, silero

from session_rules import SilenceTimer, is_closing_phrase

load_dotenv()
log = logging.getLogger("gerdoo-voice")

SYSTEM_PROMPT = (
    "You are Gerdoo, a small home robot. You are warm, brief and a little "
    "playful. Keep answers to a couple of sentences unless asked for more — "
    "you are speaking aloud, not writing. "
    "You are addressed in Persian or English. Always reply in the same "
    "language you were addressed in. Never mention that you are an AI model."
)

SILENCE_TIMEOUT_S = 30.0


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(
        stt=elevenlabs.STT(
            api_key=os.environ["ELEVEN_API_KEY"],
            # Auto-detect: the household is bilingual and the speaker may
            # switch between utterances.
            language_code=None,
        ),
        llm=openai.LLM(
            base_url=os.environ["LITELLM_BASE_URL"],
            api_key=os.environ["LITELLM_API_KEY"],
            model=os.environ["LITELLM_MODEL"],
        ),
        tts=elevenlabs.TTS(
            api_key=os.environ["ELEVEN_API_KEY"],
            model="eleven_multilingual_v2",
        ),
        vad=silero.VAD.load(),
    )

    timer = SilenceTimer(timeout_s=SILENCE_TIMEOUT_S, now=time.monotonic())

    @session.on("user_input_transcribed")
    def _on_user_speech(ev):
        # Only final transcripts count. Partials are unstable, and acting on
        # them is what made the wake word fire mid-sentence (see logs/013).
        if not getattr(ev, "is_final", False):
            return
        timer.mark_user_spoke(now=time.monotonic())
        text = getattr(ev, "transcript", "") or ""
        log.info("user: %s", text)
        if is_closing_phrase(text):
            log.info("closing phrase heard, ending session")
            ctx.add_shutdown_callback(lambda: None)
            session.interrupt()
            ctx.shutdown(reason="closing phrase")

    async def _watch_silence():
        import asyncio
        while True:
            await asyncio.sleep(1.0)
            if timer.expired(now=time.monotonic()):
                log.info("silence timeout after %.0fs, ending session",
                         timer.timeout_s)
                ctx.shutdown(reason="silence timeout")
                return

    await session.start(agent=Agent(instructions=SYSTEM_PROMPT), room=ctx.room)

    import asyncio
    asyncio.create_task(_watch_silence())

    await session.generate_reply(
        instructions="Greet the user briefly by name — they are "
                     f"{os.environ.get('AGENT_USER_NAME')} — and "
                     "ask what they need. One short sentence."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

- [ ] **Step 2: Install the one missing dependency**

Run: `pip3 install python-dotenv`
Expected: installs, or reports it is already satisfied.

- [ ] **Step 3: Create the real .env**

```bash
cp voice-agent/.env.example voice-agent/.env
```

Then edit `voice-agent/.env` and fill in `ELEVEN_API_KEY` and `LITELLM_API_KEY`. The file is gitignored.

- [ ] **Step 4: Verify the agent starts and registers**

With `livekit-server` still running from Task 1:

Run: `cd voice-agent && python3 agent.py dev`
Expected: `registered worker` in the log, and no traceback. A `KeyError` here means a key is missing from `.env`.

- [ ] **Step 5: Hold a conversation with no robot involved**

In another terminal:

```bash
export LIVEKIT_URL=ws://localhost:7880
export LIVEKIT_API_KEY=<your-api-key>
export LIVEKIT_API_SECRET=<your-api-secret>
lk room join --identity tester --publish-mic gerdoo
```

Expected: the agent joins, greets you aloud, and answers when you speak. Say "goodbye" and confirm the session ends.

This is the whole pipeline — STT, LLM, TTS — verified before the robot is touched. If it fails here, the problem is not the robot.

- [ ] **Step 6: Write the README**

Create `voice-agent/README.md`:

```markdown
# Gerdoo voice agent

Runs on the Mac. The Jetson only joins the room — see
`docs/superpowers/specs/2026-08-30-livekit-voice-agent-design.md`.

## Running

Two processes, two terminals:

```bash
livekit-server --config livekit.yaml
python3 agent.py dev
```

## Testing without the robot

```bash
export LIVEKIT_URL=ws://localhost:7880
export LIVEKIT_API_KEY=<your-api-key>
export LIVEKIT_API_SECRET=<your-api-secret>
lk room join --identity tester --publish-mic gerdoo
```

## Notes

- `livekit.yaml` binds `::` on purpose. `mac-studio.local` has
  AAAA records only, so an IPv4-only listener is unreachable by name.
- `.env` holds the ElevenLabs and LiteLLM keys and is gitignored. Only the
  LiveKit key/secret is shared with the Jetson, which needs it to sign tokens.
- Unit tests: `python3 -m pytest tests/ -v`
```

- [ ] **Step 7: Commit**

```bash
git add voice-agent/agent.py voice-agent/README.md
git commit -m "feat(voice): livekit agent worker — elevenlabs stt/tts, litellm brain"
```

---

### Task 4: Flask voice routes and token minting (TDD)

**Files:**
- Create: `robot-face/voice.py`
- Create: `robot-face/tests/test_voice.py`
- Modify: `robot-face/app.py` — add routes after `/api/events` (currently ends line 205)

**Interfaces:**
- Consumes: `broadcast(payload)` and `save_state`/`load_state` from `app.py` (defined at `robot-face/app.py:114`, `:104`, `:95`)
- Produces:
  - `voice.mint_token(room, identity, api_key, api_secret, ttl_s=3600) -> str`
  - `voice.VOICE_STATES: frozenset[str]`
  - `voice.is_valid_state(s: str) -> bool`
  - Routes `POST /api/voice/wake`, `POST /api/voice/state`, `GET /api/voice/status`

- [ ] **Step 1: Write the failing tests**

Create `robot-face/tests/test_voice.py`:

```python
import time

import jwt
import pytest

import voice

KEY = "<your-api-key>"
SECRET = "<your-api-secret>"


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd robot-face && python3 -m pytest tests/test_voice.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'voice'`

- [ ] **Step 3: Write the implementation**

Create `robot-face/voice.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd robot-face && python3 -m pytest tests/test_voice.py -v`
Expected: PASS, 17 passed

- [ ] **Step 5: Add the routes to app.py**

In `robot-face/app.py`, add `import voice` beside the other imports at the top of the file. Then insert after the `/api/events` route (which ends at line 205, just before the `# ---- Auth ----` comment):

```python
# ---- Voice sessions ----
# The room is fixed: one robot, one conversation. The agent on the Mac is
# auto-dispatched when this room is created, so joining is all the robot does.
VOICE_ROOM = "gerdoo"


def _voice_cfg():
    cfg = load_config()
    return (
        cfg.get("livekit_url", "ws://mac-studio.local:7880"),
        cfg.get("livekit_api_key", ""),
        cfg.get("livekit_api_secret", ""),
    )


def _set_voice(state):
    """Update voice state and push it to the face over the existing SSE."""
    s = load_state()
    s["voice"] = state
    s["updated"] = time.time()
    save_state(s)
    broadcast(s)
    return s


@app.route("/api/voice/wake", methods=["POST"])
def api_voice_wake():
    """Called by the wake-word service. Mints a token and tells the face to join."""
    url, key, secret = _voice_cfg()
    token = voice.mint_token(VOICE_ROOM, "face", key, secret)
    _set_voice("connecting")
    return jsonify({"url": url, "token": token, "room": VOICE_ROOM})


@app.route("/api/voice/state", methods=["POST"])
def api_voice_state():
    """Called by the browser as the session progresses."""
    data = request.get_json(force=True, silent=True) or {}
    state = data.get("voice")
    if not voice.is_valid_state(state):
        return jsonify({"error": "unknown voice state", "got": state}), 400
    return jsonify(_set_voice(state))


@app.route("/api/voice/status")
def api_voice_status():
    """Polled by the wake-word service so it knows when to resume listening."""
    return jsonify({"voice": load_state().get("voice", "idle")})
```

- [ ] **Step 6: Verify the routes by hand**

Deploy and restart, then:

```bash
scp robot-face/voice.py robot-face/app.py user@<robot-ip>:~/robot-face/
ssh user@<robot-ip> 'systemctl --user restart robot-face 2>/dev/null || pkill -f "python3 app.py"'
```

Then:

```bash
ssh user@<robot-ip> 'curl -sS -XPOST localhost:8080/api/voice/wake | head -c 200; echo
curl -sS localhost:8080/api/voice/status; echo
curl -sS -XPOST -H "Content-Type: application/json" -d "{\"voice\":\"listening\"}" localhost:8080/api/voice/state | head -c 120; echo
curl -sS -XPOST -H "Content-Type: application/json" -d "{\"voice\":\"banana\"}" -o /dev/null -w "%{http_code}\n" localhost:8080/api/voice/state'
```

Expected: a JSON object with `url`/`token`/`room`; then `{"voice": "connecting"}`; then a state object containing `"voice": "listening"`; then `400`.

- [ ] **Step 7: Commit**

```bash
git add robot-face/voice.py robot-face/tests/test_voice.py robot-face/app.py
git commit -m "feat(voice): flask token minting and voice-state routes"
```

---

### Task 5: LiveKit client in the face kiosk

**Files:**
- Modify: `robot-face/templates/face.html` — the `<script>` block starts at line 30
- Modify: the `~/.robotface-ff` Firefox profile on the Jetson

**Interfaces:**
- Consumes: `POST /api/voice/wake`, `POST /api/voice/state` from Task 4; the `voice` field arriving over `/api/events`
- Produces: a browser that joins the room whenever it sees `voice: "connecting"`, and reports its own state back

- [ ] **Step 1: Set the Firefox prefs**

A kiosk has nobody to click Allow. On the Jetson, append to `~/.robotface-ff/user.js` (create it if absent):

```javascript
// Kiosk: nobody is present to grant microphone permission.
user_pref("media.navigator.permission.disabled", true);
// Agent audio must play without a user gesture.
user_pref("media.autoplay.default", 0);
```

Then restart Firefox so the prefs take effect.

- [ ] **Step 2: Add the LiveKit SDK and the client**

In `robot-face/templates/face.html`, add before the existing `<script>` at line 30:

```html
<script src="https://cdn.jsdelivr.net/npm/livekit-client@2/dist/livekit-client.umd.min.js"></script>
```

Then inside the existing `<script>` block, after the `apply(state)` function, add:

```javascript
    // ---- Voice session -------------------------------------------------
    // The client lives in the browser rather than in a Python service on the
    // Jetson for one reason: the speaker sits beside the microphone, and
    // WebRTC gives us echo cancellation for free. Without it the robot
    // transcribes its own voice and talks to itself.
    let room = null;

    async function report(voiceState) {
      try {
        await fetch('/api/voice/state', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ voice: voiceState }),
        });
      } catch {}
    }

    async function joinVoice() {
      if (room) return;                       // already in a session
      try {
        const res = await fetch('/api/voice/wake', { method: 'POST' });
        const { url, token } = await res.json();

        room = new LivekitClient.Room({
          adaptiveStream: true,
          audioCaptureDefaults: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

        room.on(LivekitClient.RoomEvent.TrackSubscribed, (track) => {
          if (track.kind === 'audio') track.attach();   // plays agent speech
        });
        room.on(LivekitClient.RoomEvent.ActiveSpeakersChanged, (speakers) => {
          const agentTalking = speakers.some(s => s.identity !== 'face');
          report(agentTalking ? 'speaking' : 'listening');
        });
        room.on(LivekitClient.RoomEvent.Disconnected, () => {
          room = null;
          report('idle');
        });

        await room.connect(url, token);
        await room.localParticipant.setMicrophoneEnabled(true);
        report('listening');
      } catch (e) {
        room = null;
        report('error');
        setTimeout(() => report('idle'), 3000);
      }
    }

    async function leaveVoice() {
      if (!room) return;
      try { await room.disconnect(); } catch {}
      room = null;
    }
```

- [ ] **Step 3: Drive it from the SSE state**

Replace the existing `apply(state)` function with:

```javascript
    let lastVoice = 'idle';

    function apply(state) {
      if (!state) return;
      if (state.mood)  face.setAttribute('emotion', state.mood);
      if (state.color) face.setAttribute('color', state.color);

      const v = state.voice || 'idle';
      if (v !== lastVoice) {
        lastVoice = v;
        if (v === 'connecting') joinVoice();
        if (v === 'idle') leaveVoice();
      }
    }
```

- [ ] **Step 4: Deploy and test by hand**

```bash
scp robot-face/templates/face.html user@<robot-ip>:~/robot-face/templates/
ssh user@<robot-ip> 'curl -sS -XPOST localhost:8080/api/voice/wake >/dev/null'
```

Expected: the robot greets you aloud within a couple of seconds, and you can hold a conversation. `livekit-server` and `agent.py` must both be running on the Mac.

- [ ] **Step 5: Verify echo cancellation — the test this design exists for**

With the speaker at normal volume, let the robot speak a long reply and stay silent yourself. Watch the agent log on the Mac.

Expected: **no** user transcript appears while the robot is talking. If the agent transcribes its own speech, echo cancellation is not active — check that the browser is genuinely the client, and that `audioCaptureDefaults` was applied.

- [ ] **Step 6: Commit**

```bash
git add robot-face/templates/face.html
git commit -m "feat(voice): livekit client in the face kiosk, with echo cancellation"
```

---

### Task 6: Wake-word trigger, with pause and resume

**Files:**
- Modify: `wake-word/wake_word.py` — the trigger branch at lines 339-344
- Modify: `wake-word/wake-word.service`

**Interfaces:**
- Consumes: `POST /api/voice/wake` and `GET /api/voice/status` from Task 4
- Produces: nothing later tasks depend on

- [ ] **Step 1: Add the trigger call and the pause loop**

In `wake-word/wake_word.py`, add to the imports:

```python
import urllib.request
```

Add these functions beside `play()`:

```python
def start_voice_session(base_url, timeout=5.0):
    """Ask Flask to start a session. Returns True if it accepted."""
    try:
        req = urllib.request.Request(f"{base_url}/api/voice/wake", method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception as e:
        print(f"  voice wake failed: {e}", file=sys.stderr)
        return False


def voice_state(base_url, timeout=3.0):
    try:
        with urllib.request.urlopen(f"{base_url}/api/voice/status", timeout=timeout) as r:
            return json.loads(r.read()).get("voice", "idle")
    except Exception:
        return "idle"      # unreachable Flask must not wedge the detector


def wait_for_session_end(base_url, poll_s=1.0, max_s=600.0):
    """
    Block until the session is over.

    The detector must not listen during a conversation, or it hears the
    conversation and re-triggers on it. Polling rather than a push because this
    is a plain audio loop with no server in it; one request a second costs
    nothing. max_s is a backstop so a wedged session cannot deafen the robot
    permanently.
    """
    start = time.time()
    while time.time() - start < max_s:
        if voice_state(base_url) == "idle":
            return True
        time.sleep(poll_s)
    print("  session did not end within the backstop; resuming anyway",
          file=sys.stderr)
    return False
```

Add the CLI option beside the others:

```python
    ap.add_argument("--voice-url", default=None,
                    help="base URL of the robot-face Flask app, e.g. "
                         "http://localhost:8080. When set, a trigger starts a "
                         "LiveKit session and the detector pauses until it ends")
```

- [ ] **Step 2: Wire it into the trigger branch**

In the live loop, replace:

```python
                play(args.sound)
                rec.Reset()
```

with:

```python
                play(args.sound)
                rec.Reset()

                if args.voice_url:
                    if start_voice_session(args.voice_url):
                        print("  session started; detector paused", flush=True)
                        if logfh:
                            logfh.write("  session started; detector paused\n")
                        wait_for_session_end(args.voice_url)
                        print("  session ended; listening again", flush=True)
                        if logfh:
                            logfh.write("  session ended; listening again\n")
                        # Audio queued during the conversation is stale and
                        # would be decoded as if it had just been spoken.
                        with q.mutex:
                            q.queue.clear()
                        rec.Reset()
                        last_fire = time.time()
```

- [ ] **Step 3: Point the service at Flask**

In `wake-word/wake-word.service`, add to the `ExecStart` continuation:

```
    --voice-url http://localhost:8080 \
```

- [ ] **Step 4: Deploy and test end to end**

```bash
scp wake-word/wake_word.py wake-word/wake-word.service user@<robot-ip>:~/wake-word/
ssh user@<robot-ip> 'cp ~/wake-word/wake-word.service ~/.config/systemd/user/ \
  && systemctl --user daemon-reload && systemctl --user restart wake-word'
```

Then say "Gerdoo, baba".

Expected: janam.mp3 plays, the face goes amber then cyan, and the robot greets you. Talk for a minute and confirm the detector does **not** re-trigger mid-conversation. Say "goodbye" and confirm the face returns to idle and the wake word starts working again.

- [ ] **Step 5: Test the other session-end path — silence**

Say "Gerdoo, baba", let the robot greet you, then say nothing at all.

Expected: after ~30 s the session ends on its own, the face returns to idle,
and the wake word starts working again. The agent log on the Mac should show
`silence timeout after 30s, ending session`.

This is the path that matters most: it is the one that guarantees a live
microphone cannot be left open because a closing phrase was missed.

- [ ] **Step 6: Confirm the pause actually happened**

```bash
ssh user@<robot-ip> 'tail -20 ~/wake-word/triggers.log'
```

Expected: one `TRIGGER` line, then `session started; detector paused`, then `session ended; listening again` — and **no** further TRIGGER lines in between.

- [ ] **Step 7: Commit**

```bash
git add wake-word/wake_word.py wake-word/wake-word.service
git commit -m "feat(voice): wake word starts a session and pauses for its duration"
```

---

### Task 7: Visual states

**Files:**
- Modify: `robot-face/templates/face.html`

**Interfaces:**
- Consumes: the `voice` field from `/api/events`
- Produces: nothing later tasks depend on

- [ ] **Step 1: Add the colour map and apply it**

In `face.html`, add above `apply(state)`:

```javascript
    // Colours the face takes on during a voice session. `connecting` and
    // `error` are the two that must be legible from across the room — they are
    // the states where you would otherwise be staring at a face wondering what
    // happened. The rest are ambient feedback.
    const VOICE_LOOK = {
      idle:       null,                                  // fall back to normal state
      connecting: { color: '#FFAE1E', emotion: 'thinking',  pulse: true  },
      listening:  { color: '#2AD4FF', emotion: 'curious',   pulse: false },
      thinking:   { color: '#FFD34D', emotion: 'thinking',  pulse: false },
      speaking:   { color: '#37D67A', emotion: 'happy',     pulse: false },
      error:      { color: '#FF3B30', emotion: 'sad',       pulse: false },
    };
```

Then extend `apply(state)` so the voice look wins while a session is active:

```javascript
    function apply(state) {
      if (!state) return;

      const v = state.voice || 'idle';
      const look = VOICE_LOOK[v];

      if (look) {
        face.setAttribute('color', look.color);
        face.setAttribute('emotion', look.emotion);
        document.body.classList.toggle('pulse', !!look.pulse);
      } else {
        document.body.classList.remove('pulse');
        if (state.mood)  face.setAttribute('emotion', state.mood);
        if (state.color) face.setAttribute('color', state.color);
      }

      if (v !== lastVoice) {
        lastVoice = v;
        if (v === 'connecting') joinVoice();
        if (v === 'idle') leaveVoice();
      }
    }
```

- [ ] **Step 2: Add the pulse animation**

In the `<style>` block near the top of `face.html`, add:

```css
    @keyframes voicePulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.55; } }
    body.pulse robot-face { animation: voicePulse 1.4s ease-in-out infinite; }
```

- [ ] **Step 3: Walk every state by hand**

```bash
scp robot-face/templates/face.html user@<robot-ip>:~/robot-face/templates/
ssh user@<robot-ip> 'for s in connecting listening thinking speaking error idle; do
  echo "-- $s"
  curl -sS -XPOST -H "Content-Type: application/json" -d "{\"voice\":\"$s\"}" \
    localhost:8080/api/voice/state >/dev/null
  sleep 3
done'
```

Expected: the face steps through amber-pulsing, cyan, yellow, green, red, then back to its normal look. Watch the screen while this runs.

Note this drives the states directly without a real session, so `connecting` will try to join a room. That is fine — it will error out to red if the Mac is not running, which is itself a useful check.

- [ ] **Step 4: Commit**

```bash
git add robot-face/templates/face.html
git commit -m "feat(voice): visual states for the voice session"
```

---

## Done when

- Saying "Gerdoo, baba" starts a conversation and the face shows it
- The robot does not transcribe its own speech
- The detector does not re-trigger during a conversation
- Both "goodbye" and 30 s of silence end the session, and the wake word resumes
- Both test suites pass. They must be run from inside their own directory —
  `python3 -m pytest` puts the working directory on `sys.path`, which is how
  `session_rules` and `voice` get imported. Running from the repo root fails:

  ```bash
  (cd voice-agent && python3 -m pytest tests/ -v)
  (cd robot-face  && python3 -m pytest tests/ -v)
  ```
