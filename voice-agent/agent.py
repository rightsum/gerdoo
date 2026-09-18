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
import json
import re
import time

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    RunContext,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)
from livekit.plugins import elevenlabs, openai, silero

from livekit.agents import function_tool

import local_time
import video_control
import web_search
from session_rules import SilenceTimer, is_closing_phrase


@function_tool
async def what_time_is_it(context: RunContext, when: str = "today") -> str:
    """
    The current time, and the date of any day referred to relatively.

    Always returns BOTH the Gregorian and the Persian (Jalali) date. Use it for
    the time, the date, the day of the week, and — importantly — to turn a
    relative reference into a real date before searching for something that
    happened then. Do not guess; you have no clock of your own.

    Args:
        when: Which day. "today" by default. Also understands "yesterday",
            "tomorrow", "last week", "next week", "last month", "N days ago",
            "in N weeks", and similar.
    """
    out = local_time.describe(when)
    _trace(f"TIME[{when}]: {out}")
    return out


@function_tool
async def look_it_up(context: RunContext, query: str) -> str:
    """
    Search the web for current information.

    Use this for anything you cannot know: today's news, weather, prices,
    sports results, when something is open, or any fact that changes over time.
    Do not use it for chat, opinions, or things you already know.

    Args:
        query: What to search for. A short phrase works best. Write it in
            English even when the conversation is in Persian — search engines
            index far more in English — but answer in the user's language.
    """
    _trace(f"SEARCH: {query!r}")
    result = await web_search.search(query)
    _trace(f"SEARCH returned {len(result)} chars")
    return result


# Set by play_video. The entrypoint waits on it and shuts the session down once
# she has finished speaking: the video wants the screen and the speaker, and a
# call sitting on top of it would both compete for audio and hold the face.
end_call = asyncio.Event()


@function_tool
async def play_video(context: RunContext, query_or_url: str,
                     start_at: str = "") -> str:
    """
    Play a YouTube video on the robot's own screen.

    Use it when asked to play, show, or put on a video, a song, a clip or a
    film. The conversation ENDS when you do this — the video takes the screen —
    so say one short sentence confirming what you are playing, and nothing else
    afterwards.

    Args:
        query_or_url: A YouTube URL, or what to search for. A search phrase
            works best as the words a person would type: artist and title.
        start_at: Optional point to start at, like "1:30" or "90". Leave empty
            to start at the beginning.
    """
    out = await asyncio.to_thread(video_control.play, query_or_url,
                                  start_at or None)
    _trace(f"PLAY VIDEO {query_or_url!r} -> {out}")
    if not out.get("ok"):
        return f"Could not play it: {out.get('error', 'unknown error')}"
    end_call.set()
    title = out.get("title") or "it"
    return (f"Playing {title} now. Tell the user in one short sentence, then "
            "stop talking — the call is ending and the video is starting.")


@function_tool
async def stop_video(context: RunContext) -> str:
    """
    Stop whatever video is playing on the robot's screen.

    Use it when asked to stop, close, or turn off the video.
    """
    out = await asyncio.to_thread(video_control.stop)
    _trace(f"STOP VIDEO -> {out}")
    if not out.get("ok"):
        return f"Could not stop it: {out.get('error', 'unknown error')}"
    return "Stopped."


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
    "Never mention that you are an AI model.\n\n"
    "LOOKING THINGS UP:\n"
    "- You have a web search tool. Use it whenever the answer depends on "
    "current information you cannot know — weather, news, prices, opening "
    "hours, results, anything that changes.\n"
    "- Do NOT use it for chat, opinions, or things you already know. "
    "Searching to answer 'how are you' is absurd.\n"
    "- You are SPEAKING the answer. Give the one or two facts that actually "
    "answer the question, in a sentence or two. Never read out a list of "
    "results, never read URLs aloud, and never say '[1]' or 'according to "
    "result two'.\n"
    "- Say something brief first if a search will take a moment, such as "
    "'بذار ببینم' or 'let me check'.\n"
    "- If the search fails or finds nothing useful, say so plainly rather "
    "than inventing an answer.\n\n"
    "VIDEO. You can play a video on your own screen with play_video, and stop it "
    "with stop_video. When you play something, the conversation ends immediately "
    "so the video can have the screen — say one short sentence about what you are "
    "playing and nothing more. If the user asks for something you cannot find, "
    "say so instead of playing something else.\n\n"
    "TIME AND DATE:\n"
    "- You have a clock tool. Use it for the time, the date, the day of the "
    "week, or anything that depends on today — never guess.\n"
    "- Speaking Persian, give the Persian date and say the time naturally. "
    "Speaking English, give the ordinary date. Do not recite both calendars "
    "unless asked.\n"
    "- Say the time the way a person would: 'ten to eleven', not '10:50:00'.\n"
    "- Both calendars are always returned. Speaking Persian, lead with the "
    "Persian date; speaking English, lead with the Gregorian. Give the other "
    "only if it is useful or asked for.\n"
    "- When someone asks about a day in relative terms — yesterday, last "
    "week, three days ago — call the clock tool FIRST to turn it into a real "
    "date, then put that date into your search. Searching for 'yesterday' "
    "finds nothing; searching for '1 September 2026' finds the news.\n\n"
    "ANSWER LENGTH ON REQUEST:\n"
    "- If someone asks for an answer of a given length — 'in 30 seconds', "
    "'briefly', 'in one sentence', 'tell me everything' — obey it. Around 70 "
    "spoken words is roughly 30 seconds.\n"
    "- A request for a summary of several things is still speech: give the "
    "headline of each in a sentence, not a numbered list read aloud."
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
# Personal values — the user's name, credentials — stay in .env, never here.
# Optional; if unset the greeting is warm but nameless.
USER_NAME = os.environ.get("AGENT_USER_NAME", "").strip()

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
    # The worker process is reused between jobs, so a flag left set by a
    # previous call's play_video would end this new call the instant it began.
    end_call.clear()
    await ctx.connect()
    _trace("connected to room")

    # Wait for the robot to actually be in the room before saying anything.
    # Greeting into an empty room produces a speech handle that completes
    # immediately with zero chat items — no error, just silence.
    participant = await ctx.wait_for_participant()
    _trace(f"participant present: {participant.identity}")

    # The robot's panel chooses the recognition language and ships it in the
    # join token's metadata, so the setting travels with the connection rather
    # than needing a second call back to the Jetson.
    #
    # "auto" is convenient for a bilingual household but mis-hears SHORT Persian
    # utterances as Portuguese, which the model then has to apologise for.
    # Pinning removes that at the cost of the other language.
    stt_language = None
    try:
        meta = json.loads(participant.metadata or "{}")
        choice = meta.get("stt_language", "auto")
        stt_language = None if choice == "auto" else choice
    except Exception as e:
        _trace(f"could not read participant metadata: {e}")
    _trace(f"stt language: {stt_language or 'auto-detect'}")

    session = AgentSession(
        stt=elevenlabs.STT(
            api_key=os.environ["ELEVEN_API_KEY"],
            # Auto-detect: the household is bilingual and the speaker may
            # switch between utterances.
            language_code=stt_language,
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
        # Barge-in is ON, with LiveKit's default thresholds. You can talk over
        # her and she stops.
        #
        # Echo is handled entirely by the robot's XVF3800 microphone array,
        # which cancels the speaker in hardware on the same clock it plays on.
        # Nothing in this agent tries to recognise or filter her own voice.
        turn_handling={
            "interruption": {
                "enabled": True,
                # "vad", not "adaptive": adaptive calls out to LiveKit Cloud
                # (agent-gateway.livekit.cloud) and this server is self-hosted,
                # so it 401s, retries, and falls back to VAD anyway — after
                # burning a couple of seconds on every session.
                "mode": "vad",
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
        # them is what made the wake word fire mid-sentence.
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
        agent=Agent(instructions=SYSTEM_PROMPT,
                    tools=[look_it_up, what_time_is_it, play_video, stop_video]),
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
        new = getattr(ev, "new_state", "?")
        _trace(f"USER STATE: {getattr(ev, 'old_state', '?')} -> {new}")
        # Reset the hang-up clock the moment someone STARTS talking, not when
        # their sentence finishes transcribing. Waiting for the transcript lost
        # a real question: the user began speaking two seconds before the
        # timeout, the transcript landed one second after the session had begun
        # closing, and the answer was dropped with "speech scheduling is
        # paused".
        if new == "speaking":
            timer.mark_user_spoke(now=time.monotonic())

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

    async def _watch_end_call():
        """A video was requested. Let her finish the sentence, then hang up."""
        await end_call.wait()
        while session.agent_state in ("speaking", "thinking"):
            await asyncio.sleep(0.2)
        _trace("ending the call so the video can start")
        ctx.shutdown(reason="video requested")
        finished.set()

    ender = asyncio.create_task(_watch_end_call())
    _background.add(ender)
    ender.add_done_callback(_background.discard)

    if GREET:
        try:
            if USER_NAME:
                greeting = (f"Greet the user briefly by name — they are "
                             f"{USER_NAME} — and ask what they need. "
                             "One short sentence.")
            else:
                greeting = ("Greet the user briefly and warmly, and ask what "
                             "they need. One short sentence.")
            handle = session.generate_reply(instructions=greeting)
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