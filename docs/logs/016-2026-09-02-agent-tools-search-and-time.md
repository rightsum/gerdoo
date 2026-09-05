# 016 — Giving the agent tools: web search and a clock

| | |
|---|---|
| **Date** | 2026-09-02 |
| **Type** | Feature — agent tools |
| **Status** | ✅ Working |
| **Severity** | Routine |

---

## What changed

The agent could talk but not act. It now has two tools, and they compose: ask
what happened yesterday and it resolves the date, then searches for it.

| Tool | Purpose |
|---|---|
| `look_it_up` | Web search via Ollama's hosted API |
| `what_time_is_it` | Current time, and any relatively-referenced date, in both calendars |

Verified end to end: *"the news about Iran yesterday, in 30 seconds"* → resolves
yesterday to a real date → searches that date → summarises in Persian.

## Search, shaped for speech

That shaping is the whole design problem. The API returns roughly 3 KB of page
text per result, and handing that to a model produces a long, list-shaped answer
that is miserable to listen to and slow to generate.

So: **3 results, 600 characters each**, whitespace collapsed, truncated on a word
boundary. The API's own defaults (5 results, full text) are wrong for voice.

The tool's docstring is what the model reads to decide when to call it, so it is
written as instructions rather than description: use it for things that change —
weather, news, prices, opening hours — and **not** for chat or opinions.
Searching to answer "how are you" is absurd, and a model will do it if not told.

It also tells the model to write the query in **English even when the
conversation is Persian**, because search indexes far more English, then answer
in the user's language.

Failures return a plain sentence rather than raising, so a network problem
produces "the search could not be completed" instead of ending the call.

`urllib` is blocking, so the request runs in a thread. A blocking HTTP call on
the session's event loop stalls the audio pipeline.

## The clock, and why it does the Persian calendar itself

"Today is the 11th of Shahrivar" is what someone asking in Farsi wants. A
Gregorian date is a non-answer. No Jalali library was installed, and the
conversion is short and well established, so it is implemented here and verified
against known dates: 2024-03-20 and 2025-03-21 are Nowruz (1403-01-01,
1404-01-01), 1979-02-11 is 1357-11-22, 2000-01-01 is 1378-10-11. A 400-day sweep
asserts the month index never leaves 1–12.

**Both calendars are always returned.** The agent leads with the Persian date in
Persian and the Gregorian in English, but it cannot say a calendar it was never
given.

**Relative dates resolve to real ones** — today, yesterday, last week, "3 days
ago", "in 2 weeks" — and anything unrecognised falls back to today rather than
erroring. This is the part that makes search useful: searching for "yesterday"
finds nothing, searching for "1 September 2026" finds the news. The prompt makes
that chaining explicit, because a model will otherwise put the word "yesterday"
straight into the query.

The prompt also honours a requested length — "in 30 seconds" is about 70 spoken
words — and says that a summary of several things is still speech: a sentence per
headline, not a numbered list read aloud.

## The silence timer hung up on a real question

The clearest bug of the day, caught from the trace:

```
11:00:17  (her answer ends)
11:00:32  USER STATE: listening -> away
11:00:45  USER STATE: away -> speaking     <- the user starts talking
11:00:47  session finished                 <- the 30s timeout fires anyway
11:00:48  USER SAID: 'رئیس جمهور ترامپ چیزی نگفته؟'
          "skipping user input, speech scheduling is paused"
```

The question was heard, transcribed, and thrown away. The timer only reset on a
**completed transcript**, and the user began speaking two seconds before the
cutoff while the transcript landed one second after shutdown began.

It now resets when VAD reports the user has **started** speaking.

> Third distinct bug in this one timer — it has counted the agent's own speech,
> ignored the agent's state, and now missed speech that had started but not
> finished. The mistake each time was treating "the user finished a sentence" as
> the signal, when the question being asked is "is anyone talking".

## Adaptive interruption needs LiveKit Cloud

`interruption.mode = "adaptive"` calls out to `agent-gateway.livekit.cloud`. This
server is self-hosted, so it 401s, retries, and falls back to VAD anyway — after
burning a couple of seconds at the start of every session. Set to `"vad"`
explicitly.

## Open

- Search results are English-heavy by design, and the model translates when
  answering in Persian. Fine for facts, weaker for quotes.
- No tool yet for the robot's own hardware — it can look things up but still
  cannot move the neck or the lights.
