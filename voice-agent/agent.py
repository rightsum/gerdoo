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
    )

    timer = SilenceTimer(timeout_s=SILENCE_TIMEOUT_S, now=time.monotonic())
    _background: set[asyncio.Task] = set()

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

            async def _say_farewell_and_end():
                session.interrupt()
                await session.generate_reply(
                    instructions="Say a one-sentence warm farewell in the "
                                 "user's language, then nothing more.",
                )
                ctx.shutdown(reason="closing phrase")

            # Held in a set: asyncio keeps only weak references to tasks, so a
            # bare local can be collected mid-flight.
            task = asyncio.create_task(_say_farewell_and_end())
            _background.add(task)
            task.add_done_callback(_background.discard)

    async def _watch_silence():
        while True:
            await asyncio.sleep(1.0)
            if timer.expired(now=time.monotonic()):
                log.info("silence timeout after %.0fs, ending session",
                         timer.timeout_s)
                ctx.shutdown(reason="silence timeout")
                return

    await session.start(
        agent=Agent(instructions=SYSTEM_PROMPT),
        room=ctx.room,
        # The browser only sees "idle" via its Disconnected handler, so the
        # room must be deleted when this session ends — otherwise the face
        # stays connected forever and the wake word never resumes.
        room_input_options=RoomInputOptions(delete_room_on_close=True),
    )

    watch = asyncio.create_task(_watch_silence())
    _background.add(watch)
    watch.add_done_callback(_background.discard)

    # generate_reply awaits playout, so this returns only once the greeting has
    # finished speaking.
    await session.generate_reply(
        instructions="Greet the user briefly by name — they are the user — and "
                     "ask what they need. One short sentence."
    )

    # The user could not have spoken before now — the robot was talking. Start
    # their 30 s window here, not at connect time, or a slow first LLM+TTS round
    # trip eats most of the budget and the session can time out before the
    # conversation has begun.
    timer.mark_user_spoke(now=time.monotonic())


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))