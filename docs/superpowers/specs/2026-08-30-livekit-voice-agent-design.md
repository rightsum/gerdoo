# LiveKit voice agent — design

| | |
|---|---|
| **Date** | 2026-08-30 |
| **Status** | Approved, not yet implemented |
| **Scope** | Wake word starts a real-time voice conversation; the heavy work runs on the Mac |

---

## Goal

Say **"Gerdoo, baba"** to the robot and have a spoken conversation with it. The face shows
what is happening — connecting, listening, thinking, speaking. Speech recognition,
language model and speech synthesis all run **on the Mac**, so the Jetson keeps its
compute for vision, SLAM and motor control.

## Decisions

Settled during brainstorming, with the reasoning, so a later reader does not re-litigate
them:

| Decision | Choice | Why |
|---|---|---|
| Trigger | Existing Persian **"Gerdoo, baba"** Vosk detector | Already built, tuned and offline. See [`logs/013`](../../../logs/013-2026-08-29-audio-and-persian-wake-word.md) |
| Session end | **Silence timeout + closing phrase** | Phrase for a clean goodbye, 30 s timeout so there is no stuck-open failure mode with a live mic |
| LLM | **LiteLLM proxy** at `https://litellm.example.com/v1`, model `glm-5.3:cloud` | OpenAI-compatible, already running |
| STT / TTS | **ElevenLabs**, both | `livekit-plugins-elevenlabs` ships `stt.py` and `tts.py` |
| Robot-side client | **LiveKit JS SDK inside the face kiosk browser** | The decisive reason is echo cancellation — see below |
| Language | **Bilingual, follow the speaker** | Multilingual STT with auto-detect, multilingual voice, system prompt replies in the language addressed |

### Why the browser, and not a Python service on the Jetson

The speaker plays the TTS and the Brio mic is right beside it. Without cancellation the
robot transcribes its own voice and talks to itself.

Firefox is **already running in kiosk mode** rendering `face.html`, and a browser gives
WebRTC echo cancellation, noise suppression and auto gain control for free. A Python
client would mean implementing AEC by hand, or going half-duplex and losing the ability
to interrupt the robot mid-sentence.

The connection states are also trivial in the browser, because the page drawing them is
the same page holding the connection.

## Architecture

```
MAC  (mac-studio.local, <mac-ip>)
  livekit-server ......... rooms / SFU, bound to ::
  agent.py ............... livekit-agents worker
                             ElevenLabs STT  ->  LiteLLM (glm-5.3:cloud)  ->  ElevenLabs TTS
                             Silero VAD + turn detector
                             owns the timeout and the closing phrase

JETSON  (<robot-ip>)
  wake-word.service ...... unchanged detector; on trigger POSTs to Flask, then pauses
  robot-face (Flask) ..... mints the JWT, holds voice state, pushes it over existing SSE
  face.html .............. LiveKit JS SDK: joins, publishes mic, plays agent audio,
                           reports state, draws the colours
```

The agent registers as a **worker** and LiveKit auto-dispatches it when the room is
created. No cross-machine RPC is needed to start a conversation: the Jetson joins a room
and the agent appears. Reconnection and crash-restart come with the worker model.

### Flow

```
idle ──"Gerdoo, baba"──▶ wake-word plays janam.mp3
                          └─▶ POST /api/voice/wake  (Flask)
                                └─▶ mint JWT, voice=connecting ──SSE──▶ face.html
                                      └─▶ face joins the room
                                            └─▶ agent auto-dispatched, greets
                                                  └─▶ conversation
                                                        │
              ┌─────────────────────────────────────────┤
              ▼                                         ▼
      30 s silence timeout                      closing phrase
              └────────────▶ agent ends session ◀───────┘
                                └─▶ face disconnects, voice=idle
                                      └─▶ wake-word resumes
```

**The wake-word service must pause while a session is live.** Otherwise it listens to the
whole conversation and re-triggers on it.

## State machine

Voice state rides on the **existing** `/api/state` + `/api/events` SSE channel as a new
`voice` field. No new transport; `face.html` already subscribes.

| State | Face | When |
|---|---|---|
| `idle` | as today, auto moods | wake-word listening |
| `connecting` | amber, slow pulse | token minted, joining |
| `listening` | cyan, steady | agent connected, user's turn |
| `thinking` | existing `thinking` mood | LLM generating |
| `speaking` | warm green | TTS playing |
| `error` | red ~3 s, then `idle` | join failed, no agent, network gone |

No separate `connected` state — it would flash past in milliseconds on the way to
`listening`. `connecting` and `error` are the two that must be visible, because those are
the states where the user would otherwise stare at a face wondering what happened.

**Ownership**, so nothing fights over one value: the **browser** owns every state from
`connecting` onward and reports it to Flask. **Flask** owns `idle`. The wake-word service
only ever *requests* a session; it never sets state.

**Session end is decided by the agent** in both cases, because the wake-word service is
paused and cannot hear the closing phrase.

- **Closing phrase** — a **case-insensitive substring match on the final STT transcript**,
  not an LLM intent call. Deterministic, costs nothing, and cannot be talked out of
  ending by a chatty model. Matches: «خداحافظ», "khodahafez", "goodbye". The agent speaks
  a short farewell, then disconnects.
- **Timeout** — 30 s measured from the **end of the last user utterance**, not from the
  end of the agent's reply. Waiting for the user to speak is the thing being timed, so a
  long answer from the robot does not eat the window.

## Components

### Mac — new `voice-agent/` in this repo

| File | Purpose |
|---|---|
| `agent.py` | The worker: STT → LLM → TTS, VAD, turn detection, timeout, closing phrase |
| `livekit.yaml` | Server config. **Binds `::`** — see the IPv6 note below |
| `.env.example` | `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `ELEVEN_API_KEY`, `LITELLM_API_KEY`. The real `.env` is gitignored |
| `README.md` | How to start both processes |

### Jetson — changes to existing files, no new services

**`robot-face/app.py`** gains three routes:

| Route | Purpose |
|---|---|
| `POST /api/voice/wake` | Wake-word calls this. Mints the JWT, sets `voice=connecting`, returns the token and server URL |
| `POST /api/voice/state` | Browser reports `listening` / `thinking` / `speaking` / `error` / `idle` |
| `GET /api/voice/status` | So the wake-word service can tell when the session ended |

**`robot-face/templates/face.html`** gains the LiveKit JS SDK: join on `connecting`,
publish the mic, play agent audio, report state back, drive the colours.

**`wake-word/wake_word.py`** gains a trigger action — POST to Flask in addition to playing
the sound, then **pause and poll `/api/voice/status`** until idle. Polling rather than a
push because the detector is a plain loop with no server in it; one request per second
while paused costs nothing.

## Constraints and risks

**IPv6-only hostname.** `mac-studio.local` resolves to AAAA records only —
no A record. `livekit-server` binds IPv4 by default, so it must be configured to listen
on `::`, or the Jetson must use `<mac-ip>`. Measured latency Jetson→Mac is ~21 ms
with ~11 ms jitter over wifi, which is fine for voice.

**`getUserMedia` needs a secure context.** The kiosk loads `http://localhost:8080/` and
**localhost counts as secure**, so this works as deployed. The same page opened from
another machine over plain HTTP silently gets no microphone — expect that during
debugging.

**Kiosk Firefox has nobody to click Allow.** Two prefs in the `~/.robotface-ff` profile:
- `media.navigator.permission.disabled` — microphone without a prompt
- `media.autoplay.default = 0` — agent audio without a user gesture

**Dependency upgrade already applied.** `livekit-agents` 1.2.8 → 1.7.1 on the Mac, plus
`elevenlabs`, `silero` and `turn-detector` plugins at matching 1.7.1. This pulled `openai`
1.66.3 → 2.54.0 and **broke an existing pin**: `langchain-openai 0.3.9` requires
`openai<2.0.0`. Unresolved. The voice agent should get its own venv so this stops
recurring.

**Secrets.** The LiveKit API key/secret is shared — the Mac signs with it, Flask mints
tokens with it. ElevenLabs and LiteLLM keys stay on the Mac; the Jetson never sees them.

## Build order

Each step is testable on its own, so a failure localises:

1. `livekit-server` running on the Mac; `lk` CLI proves a room can be joined
2. `agent.py` alone, verified with `lk` as the other participant — no robot involved
3. Flask routes and token minting, verified with `curl`
4. `face.html` joins and holds a conversation, triggered by hand
5. Wake-word wired to the trigger, including pause and resume
6. Visual states last, once the pipeline works

## Testing

- **Agent in isolation:** `lk room join` from the Mac; confirm STT, LLM and TTS round-trip
- **Token minting:** `curl` the Flask routes; assert the JWT has the expected room, identity and grants
- **Echo:** hold a session with the speaker at normal volume and confirm the robot does not transcribe its own TTS. This is the failure the whole browser decision exists to prevent, so it gets an explicit test
- **Session end:** both paths — 30 s silence, and the closing phrase
- **Wake-word pause:** talk through a whole session and confirm no re-trigger, and that detection resumes after disconnect

## Out of scope

- Robot **actions** from conversation (moving, lights, camera). The agent talks; wiring tools comes later
- Multi-user or multi-room. One robot, one room, one conversation
- Running the agent on the Jetson. The entire point is that it does not
- Replacing the Vosk wake word with LiveKit-side turn detection
