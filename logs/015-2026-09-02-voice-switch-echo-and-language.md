# 015 — Voice switch, echo, and choosing the recognition language

| | |
|---|---|
| **Date** | 2026-09-02 |
| **Type** | Follow-up to [`014`](014-2026-09-01-livekit-voice-agent.md) — fixes and controls |
| **Status** | ✅ Conversation works, barge-in works, language selectable |
| **Severity** | Routine, with one privacy fix |

---

## Wake word fired on ordinary conversation

Roughly a third of triggers were false. The log made the cause obvious once read:

```
conf=0.52  بابا نیست اون خانم گردو آقا
conf=0.74  یه برو بیا اون بابا مامان بابا نه گرفتم بابا داره گردو بابا هست
conf=0.83  بابا میکنه الان گردو بابا میکنه گرم خیلی
```

Matching required both words **anywhere** in the transcript, not next to each other, so any sentence containing them woke the robot. Confidence did not help — the words really were recognised, just not as a phrase.

Two rules now, both replayed against the real logged transcripts:

| Rule | Why |
|---|---|
| The two words must be **adjacent** | Kills "بابا نیست اون خانم گردو آقا" |
| Utterance is at most **4 words** | Calling the robot is short. Every false positive ran 7–15 words; every genuine call was 2–3 |

**9/9 correct on real data, zero false positives, zero misses.**

## A master switch on the panel, and three bugs behind it

A **Voice** toggle now enables or disables the wake word and conversation, persisted in config so it survives restarts. Getting it working exposed three separate faults, and the second two are the interesting ones.

**Wrong session key.** The auth check used a session key this app never sets, so every POST from a browser returned 403. The switch flipped, the write never happened, and the next poll put it back.

**The status endpoint was localhost-only.** The panel's three-second poll got 403 — and the page's JavaScript read it as *enabled*:

```js
paintVoice(d.enabled !== false, d.voice)   // {"error":"forbidden"} has no
                                           // `enabled`, and undefined !== false
```

So the page was not reading the state at all; it was inventing one, then confidently painting it. The poll now requires an explicit boolean and shows `unreachable` otherwise.

> Third time in two days that a swallowed error produced a confident wrong display, after the empty `catch {}` behind the frozen face and the toggle springing back. The pattern is always the same: an error path that returns something falsy, and code that treats falsy as a valid value.

**"Off" did not release the microphone.** The switch only ignored triggers — the detector kept capturing, so the Brio's LED stayed lit and the robot was still listening. For a privacy switch that is the wrong behaviour, and the LED was the only honest indicator. It now closes the audio stream within two seconds of being switched off.

## Reverting live state without reverting the script

The setup script was still selecting the **speaker's microphone** rather than the good one, left over from an experiment that had been tried and rejected. At the time it was rejected the live state was corrected with `pactl` — but the script that recreates that state on every service start was not.

Every wake-word restart since then silently rebuilt echo cancellation on the wrong device. It surfaced as "my voice is not getting through", and for a while as *better* echo performance, which made it harder to spot.

> The script is the source of truth. A manual fix to live state is temporary by construction, and an uncommitted working tree makes this invisible — there is no diff to review.

## The speaker board has no microphone

It enumerates a USB capture endpoint and produces a steady signal, so it looks like a microphone. It is not:

| Condition | Capture RMS |
|---|---|
| A tone playing loudly through that same speaker | 0.022087 |
| Silence | 0.022050 |

Identical. A real microphone on the same board as a playing speaker would show a large difference. The constant level is electrical noise from a floating input; the USB descriptor advertises capture because the descriptor says so, not because a part is fitted.

This is why routing capture there produced a connected-looking call that transmitted nothing.

## Echo: what finally worked

The root problem is unchanged from `014` — capture and playback are separate USB devices with independent clocks, and software cancellation cannot fully bridge that. Three things helped:

**Two cancellers were running in series.** The browser had echo cancellation, noise suppression and gain control enabled, and PulseAudio's canceller was doing the same upstream. The second one's echo estimate is wrong because the first already altered the signal, and both degrade. Browser processing is now off; PulseAudio owns it.

**`extended_filter=1`** handles longer and variable echo delays, which is exactly the two-device case. It only loads **unquoted** — quoted, the module silently refuses and the setup falls back to *no cancellation at all*, which is worse than not tuning it.

**A content filter, which is what actually made barge-in usable.** Rather than relying on cancellation being good enough, the agent compares each incoming transcript against its own last three utterances and discards anything substantially similar. What leaks through cancellation is a garbled copy of the robot's own sentence, so this catches it regardless of cancellation quality:

| Input | Similarity | Result |
|---|---|---|
| Its own echo | 0.78 | ignored |
| A genuine interruption | 0.28 | passed through |

It also matches any distinctive four-word run, because echo often arrives as a fragment.

With that in place, interruption thresholds could drop to 0.6 s and 2 words without the robot interrupting itself.

## Recognition language is now a panel choice

Auto-detect mis-hears **short** Persian utterances as another language entirely and transcribes them phonetically:

```
USER SAID: 'Acabou e é só novembro'      <- actually Persian
USER SAID: 'Tá fácil, né?'               <- actually Persian
USER SAID: 'می‌تونی صداتو برام ...'       <- long utterance, perfect
```

Not a microphone problem: a bad microphone gives garbled Persian, not fluent Portuguese. Long utterances transcribe correctly.

The panel now offers **Auto-detect / Persian only / English only**, with the trade-off shown next to the control, because pinning one language costs the other — the API takes a single value, not a list.

**The choice travels in the join token's metadata**, so it reaches the agent with the connection rather than needing a second call and a second thing to authenticate. It is read when a call starts, so the UI says "applies to the next call" rather than letting a mid-call change look ignored.

## Open

- **Barge-in works but is not robust.** It rests on a content filter compensating for imperfect cancellation. One USB speakerphone with hardware AEC would make all of this unnecessary — see B13.
- **Auto-detect remains poor on short utterances.** Pinning the language is the workaround, not a fix.
- The Brio's hardware serial appears in device paths in `inventory.md` and `robot-face/camera.py`. It is a device serial, not personal data, and stable addressing depends on it.
