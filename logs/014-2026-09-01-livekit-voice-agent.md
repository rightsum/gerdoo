# 014 — LiveKit voice agent: wake word to conversation

| | |
|---|---|
| **Date** | 2026-08-30 → 2026-09-01 |
| **Type** | Feature bring-up — real-time voice |
| **Status** | ✅ Working — conversation, barge-in, bilingual |
| **Severity** | Routine |

---

## What it does

Say **"Gerdoo, baba"** → chime → a spoken conversation, back and forth, ending on
"khodahafez" / "bye" or 30 seconds where neither party speaks.

Speech recognition, the language model and speech synthesis all run **on the Mac**, so
the Jetson keeps its compute for vision and control. Design:
[`specs/2026-08-30-livekit-voice-agent-design.md`](../docs/superpowers/specs/2026-08-30-livekit-voice-agent-design.md).

```
MAC     livekit-server (rooms/SFU, bound to ::)
        agent.py — ElevenLabs STT -> LiteLLM -> ElevenLabs TTS, Silero VAD

JETSON  wake-word.service  detects, chimes, then hands over and pauses
        robot-face (Flask)  mints the JWT, carries voice state over existing SSE
        face.html           LiveKit JS joins the room, publishes the mic
```

## The audio device problems

These cost more time than everything else combined, and none were visible from the
application layer. Every one presented identically: the face reached `listening`, the
room showed both participants publishing, and the agent heard **silence**.

### 1. Two processes, one microphone

`wake_word.py` opens the Brio through **raw ALSA** and held `/dev/snd/pcmC2D0c` for the
entire call. Firefox's `getUserMedia` succeeded, PulseAudio gave it a source-output, and
it captured silence.

Pausing the detector was not enough — it stops decoding but never releases the device.
It now **closes the stream** for the duration of a call and reopens afterwards.

> Only the agent's own VAD reporting `USER STATE: listening -> away` instead of
> `-> speaking` exposed this. Nothing else in the stack showed a fault.

### 2. `module-stream-restore` silently overrides the default device

Setting PulseAudio's default source and sink **does not move an application**.
`module-stream-restore` remembers which device each app used last and re-pins it there.
Firefox therefore stayed on the raw devices, so the echo canceller sat in the path of
nothing. Now unloaded in `audio-setup.sh`.

### 3. Clock drift between two USB devices

The speaker and the Brio are **separate USB devices with independent clocks**. Echo
cancellation only works while playback and capture stay time-aligned, and PulseAudio
resyncs them every **10 seconds** by default. They drift apart in between; cancellation
collapsed after roughly thirty seconds and the robot began transcribing its own voice.

`adjust_time=1 adjust_threshold=1` resyncs every second. `adjust_threshold` must be an
integer — a float makes module load fail with a bare "Module initialization failed".

> The "it works for about thirty seconds" symptom is the signature of clock drift, not of
> a misconfiguration. It was the most useful clue in the whole exercise.

### 4. Replugging the USB hub resets everything

Re-enumeration reset the speaker's mixer to 15% and moved PulseAudio's default source to
the **speaker's own built-in microphone**. Firefox records from the default source, so the
robot went deaf while looking perfectly connected.

`wake-word/audio-setup.sh` now runs on every service start and resolves devices **by
name**, restores mixer levels, loads the echo canceller and pins the defaults. My first
version hardcoded `amixer -c 2` and only worked by luck.

> **Third time this project has been bitten by addressing a USB device by index** — after
> `/dev/ttyACM*` and PortAudio device indices. Anything USB, addressed by number, breaks
> on replug.

## Echo, and the two wrong fixes

Browser AEC cannot help: the speaker and mic are separate devices with no shared clock.
Two attempts made it worse before PulseAudio's canceller fixed it properly.

| Attempt | Result |
|---|---|
| `setMicrophoneEnabled(false)` while the agent speaks | **Stops the track and releases the hardware.** Re-acquiring every turn is a race; after a few turns the call went permanently silent while still looking connected |
| Track-level `mute()` / `unmute()` | Same failure. Churning the audio path every turn is the problem, not the mechanism |
| `turn_handling={"interruption": {"enabled": False}}` | Worked, but costs barge-in entirely |
| **`module-echo-cancel` + interruptions re-enabled** | ✅ What shipped |

Barge-in is on with thresholds above the defaults — `mode: "adaptive"`, `min_duration:
0.8`, `min_words: 2` — because residual echo is short and fragmentary, so requiring a real
utterance keeps leftovers from counting as an interruption.

## Bugs in my own code

- **The entrypoint returning ends the job.** It greeted, the coroutine fell off the end,
  and the session died — presenting exactly as "it will not hold a conversation". It now
  blocks on an `asyncio.Event` set by either ending.
- **The silence timer counted the robot's own speech.** It only reset when the *user*
  spoke, but during a story the user is silent by definition, so any answer longer than
  30 s hung up on itself mid-sentence. The window now means "nobody has spoken", and the
  watchdog refuses to fire while the agent is `speaking` or `thinking`.
- **The chime was fire-and-forget.** `janam.mp3` played while the browser joined with its
  mic already live, so the agent's first transcript was the robot hearing itself say
  "janam". The chime now finishes, plus a 0.4 s settle, before the session starts.
- **`#voice-caption` and `#voice-audio` were inside the `{% if renderer == '2d' %}`
  branch.** The robot uses the GL renderer, so both were absent, `getElementById` returned
  null, and `apply()` threw on every state change — swallowed by an empty `catch {}` in
  the SSE handler. A frozen face with no error anywhere. Both divs are now outside the
  branch and the empty catches report.
- **`track.attach()` returns a DETACHED element.** Firefox will not autoplay one outside
  the document, so the agent would have been inaudible. Elements go into a sink div.
- **The wake-word backstop cut real conversations.** A 180 s cap could not tell a wedged
  session from a good one and reclaimed the microphone mid-call. It now waits
  indefinitely on any live conversational state, and only gives up quickly when stuck on
  `connecting`.

## Flask serves a cached template

**`scp`ing `face.html` is not enough — `robot-face` must be restarted.** Jinja caches the
compiled template, so every fix looked like it had failed. Hours were spent debugging
code the browser was never running. `/` now sends `Cache-Control: no-store` as well,
because the kiosk browser also cached it and nobody is there to press reload.

## ElevenLabs Scribe tags non-speech as transcripts

`tag_audio_events` defaults to **True**, so Scribe emitted `[background noise]`,
`[phone beeping]` and `[outro jingle]` as *user transcripts*. The model answered them, and
the robot held a conversation with the room. Now `False`, plus a filter that ignores any
transcript which is only a bracketed tag.

## Models: standalone behaviour does not predict in-session behaviour

| Model | Raw HTTP | Via the plugin | In a real session |
|---|---|---|---|
| `gemini/gemini-3.5-flash-lite` | ✅ | ✅ | ✅ **shipped** |
| `gpt-4o-2024-08-06` | ✅ | ✅ | ✅ |
| `glm-5.3:cloud` | ✅ | ✅ | ✅ but 300+ reasoning tokens per reply |
| `deepseek-v4-flash:0731-cloud` | ✅ | ✅ | ❌ **empty replies** |

deepseek returns real content over raw HTTP in every request shape tried — plain,
`tools=[]`, with tools, `tool_choice`, `parallel_tool_calls` — and through the LiveKit
plugin directly. Inside a live `AgentSession` it returns `chat_items=0` instantly, with or
without the `ollama_chat/` prefix. **Cause not found.** Recorded so the next person does
not repeat the search.

## Voice and language

- **TTS model changes how a voice sounds.** The voice ID was right all along; it sounded
  wrong because we were on `eleven_multilingual_v2` while the web player used v3. Now
  `eleven_v3_conversational`, which also renders **audio tags** — `[laughs]`, `[whispers]`,
  `[sighs]` — verified working in service.
- **Scribe's auto-detect mis-identifies Persian** as French, Russian, Dutch or Norwegian on
  short utterances, and the model then replied in that language. `language_code` takes one
  value, so bilingual input means auto-detect stays. Handled in the system prompt: only
  Persian or English ever, and anything else is treated as mis-transcribed Persian.

## Debugging notes

- **Forked job processes log nowhere useful.** A job could die leaving no trace at all.
  `_trace()` appends to `/tmp/gerdoo-agent-trace.log` and was the only thing that ever made
  agent-side failures visible. Worth keeping.
- **The kiosk has no console.** `window.onerror` and breadcrumbs POST to
  `/api/voice/log`, readable with `curl`. Without it the browser is a black box.
- **`journalctl --user` is not persisted on this box**, so service stdout goes nowhere.
  Both services log to files instead.
- **Restarting the agent kills any live call** — the job fails and the face freezes in
  `listening`. Several reported failures were this, not the code.

## Open

- **Barge-in under sustained load is unproven.** AEC across two independent USB clocks is
  inherently marginal; if it degrades again the honest fix is hardware — a speakerphone
  with hardware AEC, one clock domain.
- **Conversation context does not survive a call.** Each wake word starts fresh.
- **`audio-setup.sh` runs only at service start.** If replugging is routine it should fire
  from a udev rule instead.
- **The agent has no tools.** It talks; it cannot yet move the neck or the lights.
