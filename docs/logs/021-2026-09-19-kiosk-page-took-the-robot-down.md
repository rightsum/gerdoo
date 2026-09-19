# 021 — The kiosk page took the robot down, twice

| | |
|---|---|
| **Date** | 2026-09-19 |
| **Type** | Outage — self-inflicted |
| **Status** | ✅ Fixed and deployed · 🔄 Watching for recurrence |
| **Severity** | Total: the control panel stopped answering, and with it the wake word |

---

## Symptom

Twice in one afternoon the robot went dead. The panel stopped responding, and
"گردو بابا" stopped waking anything. Every service still reported `active`.

The second time it recurred **within ten minutes** of a restart.

## What it looked like from outside

```
$ curl -m 20 localhost:8080/api/state        HTTP 000 in 20.001s
$ ss -ltn | grep 8080
LISTEN 129    128          0.0.0.0:8080
```

129 connections waiting against a backlog of 128 — the app was not accepting at
all. Yet the port was open and the process was running, hot, in state `R`.

The process itself:

```
threads: 1019      open fds: 1024      Max open files: 1024
```

Exactly at the descriptor ceiling, with a thread per descriptor. And:

```
$ ss -tn '( sport = :8080 )' | awk '{print $1}' | sort | uniq -c
     45 CLOSE-WAIT
      8 ESTAB
```

`CLOSE-WAIT` means the peer closed and this end never did. Each one is a leaked
descriptor held by a thread that never exits. `systemd-journal` sat at **97% CPU**
logging the resulting accept failures.

## Root cause — mine

`robot-face/templates/face.html`, as shipped with the voice-agent work:

```javascript
function jslog(msg) {
  try {
    fetch('/api/voice/log', { ... });     // returns a promise
  } catch {}                              // catches nothing asynchronous
}
window.onunhandledrejection = (e) => jslog(`UNHANDLED ${...}`);
```

`fetch()` rejects **asynchronously**. The `try/catch` around it never sees a
network failure, so a failed log became an unhandled rejection; the rejection
handler called `jslog`; `jslog` fetched again; that failed too.

**Every failure manufactured another failure**, each one a new connection.

The robot's own breadcrumb log caught it happening:

```
15:28:13 UNHANDLED NetworkError when attempting to fetch resource.
15:28:13 UNHANDLED NetworkError when attempting to fetch resource.
15:28:13 UNHANDLED NetworkError when attempting to fetch resource.
```

Three in the same second. That is the loop running.

So this was not a slow leak. It was an avalanche: the instant the server was slow
enough to fail one request, the kiosk page attacked it, and Flask's development
server — a thread per connection — converted the attack directly into threads and
descriptors until `accept()` failed in a tight loop.

## Why the wake word died with it

The detector was never deaf. It was attached to `gerdoo_mic` the whole time, and
its own log shows it flapping:

```
voice disabled; microphone released
voice enabled; listening again
```

That is the two-second switch poll hitting a dead server: `voice_disabled()`
treats an unreachable panel as *enabled*, so it reopened the microphone, polled
again, and flapped. And a trigger goes nowhere anyway, because `/api/voice/wake`
is on the same wedged server. **The microphone was fine; the endpoint was gone.**

## The fix

Three guards, all in `jslog`:

| Guard | Stops |
|---|---|
| `.catch(() => {})` | a failed log becoming an unhandled rejection |
| a `busy` flag | a log raised *while logging* re-entering |
| a failure counter | hammering an unreachable server — after 3 consecutive failures it stops until one succeeds |

And a seatbelt, not a fix: `LimitNOFILE=65536` on `robot-face.service`. The
default soft limit is 1024 against a 1048576 hard limit. This does not stop a
leak; it turns "dies in minutes" into "degrades over hours", which is the
difference between noticing a problem and losing the robot.

## Verification

Before, climbing steadily toward the ceiling. After deploying the page, restarting
the panel so Jinja dropped its cached template, and forcing the kiosk browser to
reload so the new JavaScript was actually running:

```
t1  fds=15  threads=10  close_wait=1
t2  fds=14  threads=9   close_wait=0
t3  fds=14  threads=9   close_wait=0
```

Flat. `Max open files` confirmed at 65536 on the running process. All four suites
green: robot-face 97 with Flask and 77 + 1 skipped without, wake-word 9,
voice-agent 61.

**Not yet proven:** that it stays flat. The failure took minutes to appear the
second time, so a quiet hour is the real test, and the kiosk page must be reloaded
after any future deploy or it keeps running the old code from cache.

## Wrong turns

- **Blamed the audio setup first.** `gerdoo_mic` had genuinely vanished again (the
  board re-enumerated, USB device 019 → 034), so it looked like the same fault as
  yesterday. It was real, and it was not the outage.
- **Blamed `broadcast()`** — proposed a blocking `put` on a full subscriber queue
  one message before reading the code, which uses `put_nowait` and discards dead
  queues. It cannot block.
- **Blamed a slow handler** — `/api/video/status` opens a socket to mpv on every
  call, so a wedged player would park threads. mpv answered its own socket in
  **14 ms**.
- **An isolation experiment measured the wrong process.** `pgrep` was run
  immediately after a restart and matched something that was not the app; every
  sample read "0 fds, now 4". Four descriptors is impossible for a live server,
  and the face-track/wake-word comparison built on it was meaningless.
- **Tried to reproduce via the reported trigger** — turning voice off — and could
  not: descriptors stayed at 13 across fifty seconds. The toggle was never the
  cause. *Any* stall would do; the page's reaction to one is what killed it.

## Takeaways

- **`try/catch` does not catch a rejected promise.** A bare `fetch()` inside a
  `try` block is unguarded, and if the error path logs, the log is another fetch.
- **Error reporting must never be able to cause errors.** A logger that reports
  failures over the network needs a re-entrancy guard and a give-up rule, or it
  becomes a denial of service against its own server the moment the network is
  the thing that is broken.
- **A thread-per-connection dev server converts any connection storm into
  descriptor exhaustion.** The ceiling is 1024 by default, which is minutes.
- **`active` is not `working`.** Every service reported healthy throughout.
- **Verify the process you are measuring is the one you mean.** Two of today's
  five measurements were void for that reason alone.
