#!/usr/bin/env bash
# Put the microphone back when it disappears, and reattach the detector to it.
#
# Why this exists: on 2026-09-19 the XVF3800 re-enumerated four times in an
# afternoon (USB device 019 → 034 → 038 → 044). Every time it does, PulseAudio
# destroys `gerdoo_mic` — the remapped source carrying the board's PROCESSED
# channel — and the wake-word detector silently reattaches to the RAW six-channel
# input instead. PulseAudio then downmixes those six channels to mono for it,
# averaging the one good channel with four un-cancelled microphones. The result
# is audio that looks healthy by every measure (clean structure, gains at
# maximum, sensible level) and is roughly four times too quiet to recognise. The
# robot simply stops answering to its name, and nothing reports an error.
#
# It also vanished twice with no USB event at all, PulseAudio having dropped the
# module on its own — which is why this runs on a timer as well as from udev.
#
# Idempotent and quiet: it prints nothing and changes nothing when all is well,
# so it is safe to run every thirty seconds forever.
set -u
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

LOG="$HOME/wake-word/audio-repair.log"
MIC_SOURCE=gerdoo_mic
SETUP="$HOME/wake-word/audio-setup.sh"
PANEL="http://localhost:8080"

note() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# 1. Does the processed source exist at all?
if ! pactl list short sources 2>/dev/null | grep -q "[[:space:]]$MIC_SOURCE[[:space:]]"; then
    note "$MIC_SOURCE missing — rebuilding"
    [ -x "$SETUP" ] && "$SETUP" >/dev/null 2>&1
    if pactl list short sources 2>/dev/null | grep -q "[[:space:]]$MIC_SOURCE[[:space:]]"; then
        note "$MIC_SOURCE rebuilt"
    else
        note "$MIC_SOURCE could NOT be rebuilt — is the board enumerated?"
        exit 0
    fi
fi

MIC_ID=$(pactl list short sources 2>/dev/null | awk -v n="$MIC_SOURCE" '$2 == n {print $1; exit}')
[ -n "${MIC_ID:-}" ] || exit 0

# 2. Is the detector actually reading from it? It holds its stream open across a
#    source being destroyed and recreated, so "running" says nothing about which
#    source it ended up on.
DET_SRC=$(pactl list source-outputs 2>/dev/null | awk '
    /^Source Output #/ { idx = $3 }
    /^[[:space:]]*Source: / { src = $2 }
    /application\.name = "ALSA plug-in \[python3/ { print src; exit }')

if [ -n "${DET_SRC:-}" ] && [ "$DET_SRC" = "$MIC_ID" ]; then
    exit 0                      # healthy: nothing to say, nothing to do
fi

# 3. Reattaching means restarting the detector, which drops its microphone —
#    never do that mid-call. A conversation is worth more than a fast repair,
#    and the next run is thirty seconds away.
VOICE=$(curl -s -m 3 "$PANEL/api/voice/status" 2>/dev/null \
        | sed -n 's/.*"voice":"\([a-z]*\)".*/\1/p')
if [ -n "${VOICE:-}" ] && [ "$VOICE" != "idle" ]; then
    note "detector on source ${DET_SRC:-none} (want $MIC_ID) but a call is live ($VOICE) — deferring"
    exit 0
fi

note "detector on source ${DET_SRC:-none}, want $MIC_ID ($MIC_SOURCE) — restarting wake-word"
systemctl --user restart wake-word >/dev/null 2>&1
sleep 4
NOW=$(pactl list source-outputs 2>/dev/null | awk '
    /^Source Output #/ { idx = $3 }
    /^[[:space:]]*Source: / { src = $2 }
    /application\.name = "ALSA plug-in \[python3/ { print src; exit }')
if [ "${NOW:-}" = "$MIC_ID" ]; then
    note "detector reattached to $MIC_SOURCE"
else
    note "detector still on source ${NOW:-none} after restart"
fi
exit 0
