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
import difflib
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
        # Interruptions OFF. This is a deliberate trade, not an oversight.
        #
        # Echo cancellation has to hold two SEPARATE USB devices in sync — the
        # Brio captures, the speaker plays — and their clocks drift apart. AEC
        # is good enough that the robot does not hear itself while it is the
        # only one talking, but not good enough to distinguish its own voice
        # from a genuine interruption. With barge-in enabled it interrupts
        # ITSELF on its own echo, which is far worse than not being
        # interruptible.
        #
        # Barge-in becomes safe the moment capture and playback share a clock:
        # one USB speakerphone with hardware AEC. Until then, half-duplex.
        turn_handling={
            "interruption": {
                "enabled": True,
                # "vad", not "adaptive": adaptive calls out to LiveKit Cloud
                # (agent-gateway.livekit.cloud) and this server is self-hosted,
                # so it 401s, retries, and falls back to VAD anyway — after
                # burning a couple of seconds on every session.
                "mode": "vad",
                # Low, because the echo filter above now catches her own
                # voice by content. What matters here is that a real
                # interruption is not missed.
                "min_duration": 0.6,
                "min_words": 2,
            }
        },
        # If she is interrupted but no real user turn follows, that was almost
        # certainly her own echo — pick up where she left off instead of
        # abandoning the answer.
        resume_false_interruption=True,
        agent_false_interruption_timeout=2.0,
    )

    timer = SilenceTimer(timeout_s=SILENCE_TIMEOUT_S, now=time.monotonic())

    # What she has recently said, so her own echo can be recognised and thrown
    # away. Echo cancellation across two USB clocks is imperfect, and what
    # leaks through is a garbled copy of her own sentence — which STT
    # transcribes and the model then answers, holding a conversation with
    # itself. Comparing against her own recent speech catches it regardless of
    # how good the cancellation is.
    recent_agent_speech: list[str] = []

    def is_own_echo(text: str) -> bool:
        norm = " ".join(text.split())
        if len(norm) < 12:
            return False        # too short to judge; let it through
        for said in recent_agent_speech[-3:]:
            if difflib.SequenceMatcher(None, norm, said).ratio() > 0.45:
                return True
            # Echo is often a fragment of a longer sentence, which ratio()
            # scores poorly, so check containment of a distinctive run too.
            words = norm.split()
            if len(words) >= 4:
                for i in range(len(words) - 3):
                    if " ".join(words[i:i + 4]) in said:
                        return True
        return False
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

        if is_own_echo(stripped):
            _trace(f"IGNORED own echo: {stripped[:80]!r}")
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
                    tools=[look_it_up, what_time_is_it]),
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
        if role == "assistant" and txt:
            recent_agent_speech.append(" ".join(str(txt).split()))
            del recent_agent_speech[:-3]
        _trace(f"ITEM [{role}]: {str(txt)[:160]!r}")
    watch = asyncio.create_task(_watch_silence())
    _background.add(watch)
    watch.add_done_callback(_background.discard)

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