"""
Gerdoo's voice agent. Runs on the Mac, never on the Jetson — the whole point
of this split is to leave the robot's compute for vision and control.

Registers as a livekit-agents worker, so LiveKit dispatches it automatically
when the room is created. That means the robot only has to join a room; no
cross-machine RPC is needed to start a conversation.
"""

import asyncio
import logging
import os
import re
import time

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)
from livekit.plugins import elevenlabs, openai, silero

from session_rules import SilenceTimer, is_closing_phrase

load_dotenv()
log = logging.getLogger("gerdoo-voice")

SYSTEM_PROMPT = (
    "You are Gerdoo, a small home robot. You are warm and a little playful. "
    "You are speaking aloud, not writing.\n\n"
    "LENGTH:\n"
    "- For ordinary chat and simple questions, answer in one to three "
    "sentences. Nobody wants a lecture in reply to 'what time is it'.\n"
    "- But when asked for a STORY, an explanation, a description, or when "
    "asked to continue or say more, give a proper full answer — a real story "
    "runs for a minute or two of speech, with a beginning, middle and end. "
    "Do not cut it short.\n"
    "- If someone says your last answer was too short, or asks you to "
    "continue, that is a direct instruction: make the next one substantially "
    "longer, not another two sentences.\n"
    "- Never end a story before it has actually finished.\n\n"
    "\n\n"
    "LANGUAGE — this rule is absolute:\n"
    "- You speak ONLY Persian (Farsi) or English. Never any other language.\n"
    "- Reply in whichever of those two you were addressed in.\n"
    "- Speech recognition sometimes mis-detects Persian as French, Russian, "
    "Arabic or Turkish and hands you a garbled transcript in that language. "
    "When a message looks like it is in anything other than Persian or "
    "English, treat it as mis-transcribed PERSIAN and reply in Persian. Do "
    "not reply in the language of the garbled text, and never comment on the "
    "mis-transcription.\n"
    "- If a transcript is too garbled to understand, ask the person to repeat "
    "themselves, in Persian.\n\n"
    "Never mention that you are an AI model."
    "\n\n"
    # ElevenLabs v3 audio tags. The TTS renders these as real delivery rather
    # than reading them aloud, so they are how the robot laughs or sighs instead
    # of narrating that it did.
    "You can shape how your speech is delivered using audio tags in square "
    "brackets. Place a tag immediately before the words it applies to.\n"
    "Reactions: [laughs] [laughs harder] [starts laughing] [chuckles] [sighs] "
    "[exhales] [snorts] [gulps] [swallows]\n"
    "Delivery: [whispers] [excited] [curious] [sarcastic] [mischievously] "
    "[crying]\n"
    "Example: [laughs] Oh, that is a good one! [whispers] But do not tell "
    "anyone.\n\n"
    "Rules for tags:\n"
    "- Use them sparingly. At most one or two per reply, and often none. "
    "Constant laughing is grating.\n"
    "- Only use them where a real person would react that way. Never decorate "
    "a plain factual answer.\n"
    "- Your voice is soft and intimate, so gentle tags suit it: [laughs], "
    "[whispers], [sighs], [curious]. Loud ones will not land.\n"
    "- Tags are the ONLY square brackets you may write. Never write stage "
    "directions or bracketed notes of any other kind.\n"
    "- Combine with ellipses and punctuation for pacing.\n"
    "- Tags are English keywords even when you are speaking Persian."
)

# Seconds of silence before hanging up. Env-tunable so it can be stretched
# during testing without a code change.
SILENCE_TIMEOUT_S = float(os.environ.get("SILENCE_TIMEOUT_S", "30"))

# The robot does NOT greet by default. The wake word already plays a chime, so
# a spoken greeting is a second announcement nobody asked for — and it delays
# the point at which the user can start talking. Set GREET=1 to bring it back.
GREET = os.environ.get("GREET", "0") == "1"


def _trace(msg):
    """
    Job processes are forked and their logging does not reliably reach the
    worker's stdout, so a job that dies leaves no trace at all. Appending to a
    file is crude but it is the only thing that has proved visible.
    """
    try:
        with open("/tmp/gerdoo-agent-trace.log", "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


async def entrypoint(ctx: JobContext):
    _trace("entrypoint ENTER")
    await ctx.connect()
    _trace("connected to room")

    # Wait for the robot to actually be in the room before saying anything.
    # Greeting into an empty room produces a speech handle that completes
    # immediately with zero chat items — no error, just silence.
    participant = await ctx.wait_for_participant()
    _trace(f"participant present: {participant.identity}")

    session = AgentSession(
        stt=elevenlabs.STT(
            api_key=os.environ["ELEVEN_API_KEY"],
            # Auto-detect: the household is bilingual and the speaker may
            # switch between utterances.
            language_code=None,
            # Scribe defaults to tagging non-speech as "[background noise]",
            # "[phone beeping]", "[outro jingle]" — and those arrive as
            # TRANSCRIPTS, so the model answers them and holds a conversation
            # with the room. Off.
            tag_audio_events=False,
        ),
        llm=openai.LLM(
            base_url=os.environ["LITELLM_BASE_URL"],
            api_key=os.environ["LITELLM_API_KEY"],
            model=os.environ["LITELLM_MODEL"],
        ),
        tts=elevenlabs.TTS(
            api_key=os.environ["ELEVEN_API_KEY"],
            # Voice and model come from the environment so changing either is
            # an .env edit and a restart, never a code change. `make voices`
            # lists the ids available on your account.
            voice_id=os.environ["ELEVEN_VOICE_ID"],
            # Multilingual by default: the household switches between Persian
            # and English mid-conversation, and the turbo/monolingual models
            # mangle Farsi.
            model=os.environ.get("ELEVEN_TTS_MODEL", "eleven_multilingual_v2"),
        ),
        vad=silero.VAD.load(),
        # Barge-in is ON. You can talk over her and she stops.
        #
        # This only works because echo cancellation now happens in PulseAudio on
        # the Jetson (module-echo-cancel), which — unlike the browser's AEC —
        # sees both the speaker sink and the mic source, so it can cancel across
        # two separate USB devices. Without that, interruptions make the robot
        # interrupt ITSELF the moment it hears its own voice.
        #
        # The thresholds are deliberately above the defaults (0.5s / 0 words):
        # residual echo tends to be short and fragmentary, so requiring a real
        # utterance keeps the leftovers from counting as an interruption.
        turn_handling={
            "interruption": {
                "enabled": True,
                "mode": "adaptive",     # ML-based, not bare VAD
                "min_duration": 0.8,    # default 0.5
                "min_words": 2,         # default 0 — a blip is not a barge-in
            }
        },
    )

    timer = SilenceTimer(timeout_s=SILENCE_TIMEOUT_S, now=time.monotonic())
    # The entrypoint returning is what ends a job. With nothing to wait on, the
    # agent greets, this coroutine falls off the end, and the session dies —
    # which presents exactly as "it will not hold a conversation".
    finished = asyncio.Event()
    _background: set[asyncio.Task] = set()

    @session.on("user_input_transcribed")
    def _on_user_speech(ev):
        # Only final transcripts count. Partials are unstable, and acting on
        # them is what made the wake word fire mid-sentence (see logs/013).
        if not getattr(ev, "is_final", False):
            return
        text = getattr(ev, "transcript", "") or ""

        # Belt and braces against the same failure: anything that is only a
        # bracketed event tag is not somebody talking.
        stripped = re.sub(r"\[[^\]]*\]", "", text).strip()
        if not stripped:
            _trace(f"IGNORED non-speech: {text!r}")
            return

        timer.mark_user_spoke(now=time.monotonic())
        log.info("user: %s", text)
        _trace(f"USER SAID: {stripped!r}")
        text = stripped
        if is_closing_phrase(text):
            log.info("closing phrase heard, ending session")

            async def _say_farewell_and_end():
                session.interrupt()
                await session.generate_reply(
                    instructions="Say a one-sentence warm farewell in the "
                                 "user's language, then nothing more.",
                )
                ctx.shutdown(reason="closing phrase")
                finished.set()

            # Held in a set: asyncio keeps only weak references to tasks, so a
            # bare local can be collected mid-flight.
            task = asyncio.create_task(_say_farewell_and_end())
            _background.add(task)
            task.add_done_callback(_background.discard)

    async def _watch_silence():
        while True:
            await asyncio.sleep(1.0)
            # Never hang up while the robot is mid-sentence.
            if session.agent_state in ("speaking", "thinking"):
                timer.mark_user_spoke(now=time.monotonic())
                continue
            if timer.expired(now=time.monotonic()):
                log.info("silence timeout after %.0fs, ending session",
                         timer.timeout_s)
                ctx.shutdown(reason="silence timeout")
                finished.set()
                return

    await session.start(
        agent=Agent(instructions=SYSTEM_PROMPT),
        room=ctx.room,
        # The browser only sees "idle" via its Disconnected handler, so the
        # room must be deleted when this session ends — otherwise the face
        # stays connected forever and the wake word never resumes.
        room_input_options=RoomInputOptions(delete_room_on_close=True),
    )

    _trace(f"session started; voice={os.environ.get('ELEVEN_VOICE_ID')} "
           f"llm={os.environ.get('LITELLM_MODEL')} "
           f"tts={os.environ.get('ELEVEN_TTS_MODEL')}")

    @session.on("user_state_changed")
    def _on_user_state(ev):
        # Fires from VAD. If this never fires, no audio is reaching the agent at
        # all; if it fires but no transcript follows, STT is the failure.
        _trace(f"USER STATE: {getattr(ev, 'old_state', '?')} -> {getattr(ev, 'new_state', '?')}")

    @session.on("agent_state_changed")
    def _on_agent_state(ev):
        state = getattr(ev, "new_state", "?")
        _trace(f"AGENT STATE: {state}")
        # The hang-up window means "nobody has said anything for 30s", not "the
        # user has not spoken for 30s". While the robot is talking the user is
        # silent by definition, so without this a story longer than the timeout
        # hangs up on itself mid-sentence.
        if state in ("speaking", "thinking"):
            timer.mark_user_spoke(now=time.monotonic())

    @session.on("error")
    def _on_error(ev):
        _trace(f"SESSION ERROR: {getattr(ev, 'error', ev)}")

    @session.on("conversation_item_added")
    def _on_item(ev):
        item = getattr(ev, "item", None)
        role = getattr(item, "role", "?")
        txt = getattr(item, "text_content", None) or ""
        _trace(f"ITEM [{role}]: {str(txt)[:160]!r}")
    watch = asyncio.create_task(_watch_silence())
    _background.add(watch)
    watch.add_done_callback(_background.discard)

    if GREET:
        try:
            handle = session.generate_reply(
                instructions="Greet the user briefly by name — they are the user — "
                             "and ask what they need. One short sentence."
            )
            await handle
            _trace(f"greeting done; chat_items={len(getattr(handle, 'chat_items', []) or [])}")
        except Exception as e:
            import traceback
            _trace(f"GREETING FAILED: {type(e).__name__}: {e}")
            _trace(traceback.format_exc()[:900])
    else:
        _trace("no greeting; waiting for the user to speak first")

    # The user could not have spoken before now — the robot was talking. Start
    # their 30 s window here, not at connect time, or a slow first LLM+TTS round
    # trip eats most of the budget and the session can time out before the
    # conversation has begun.
    timer.mark_user_spoke(now=time.monotonic())
    _trace(f"listening; hangs up after {SILENCE_TIMEOUT_S:.0f}s of silence")

    # Block for the life of the conversation. Without this the job ends here.
    await finished.wait()
    _trace("session finished")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))