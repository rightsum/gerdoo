#!/usr/bin/env bash
# Put the robot's audio devices back into a known state.
#
# Unplugging the USB hub re-enumerates everything, and that resets ALSA mixer
# levels and lets PulseAudio pick a new default source. Twice now that has
# presented as "the robot went deaf": the default source silently moved to the
# USB speaker's own microphone, so Firefox captured from the wrong device.
#
# Everything here resolves devices BY NAME. Card indices move on replug — the
# same trap as /dev/ttyACM* and PortAudio indices.
set -u
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

MIC_CARD_NAME="${MIC_CARD_NAME:-B500}"        # Brio 500
SPK_CARD_NAME="${SPK_CARD_NAME:-Device}"      # "USB2.0 Device", the speaker
SPK_LEVEL="${SPK_LEVEL:-80%}"

card_index() {   # card_index <name-in-/proc/asound/cards>
    awk -v want="$1" '$2 == "["want"" || $0 ~ "\\["want" *\\]" {print $1; exit}' /proc/asound/cards
}

MIC_CARD=$(card_index "$MIC_CARD_NAME")
SPK_CARD=$(card_index "$SPK_CARD_NAME")

if [ -n "${MIC_CARD:-}" ]; then
    # The Brio's capture gain is what makes ~4 m range possible at all.
    amixer -c "$MIC_CARD" sset Headset 100% unmute >/dev/null 2>&1
    echo "mic: card $MIC_CARD ($MIC_CARD_NAME) capture at 100%"
else
    echo "mic: card '$MIC_CARD_NAME' NOT FOUND" >&2
fi

if [ -n "${SPK_CARD:-}" ]; then
    # The hardware mixer ships at 15%, which reads as a broken speaker.
    amixer -c "$SPK_CARD" sset PCM "$SPK_LEVEL" unmute >/dev/null 2>&1
    echo "speaker: card $SPK_CARD ($SPK_CARD_NAME) PCM at $SPK_LEVEL"
else
    echo "speaker: card '$SPK_CARD_NAME' NOT FOUND" >&2
fi

# The call uses the SPEAKER's own microphone, not the Brio.
#
# Not a downgrade — it is what makes echo cancellation work at all. AEC has to
# subtract played audio from captured audio, and that only holds if both share a
# clock. The Brio and the speaker are separate USB devices with independent
# clocks, so they drift apart; cancellation held for about thirty seconds and
# then the robot started transcribing its own voice again. Capture and playback
# on ONE device cannot drift.
#
# The Brio stays dedicated to wake-word detection, which also removes the
# two-processes-one-microphone contention entirely.
SRC=$(pactl list short sources 2>/dev/null | awk '/USB2.0/ && !/monitor/ {print $2; exit}')
SINK=$(pactl list short sinks 2>/dev/null | awk '/USB2.0/ && !/monitor/ {print $2; exit}')
[ -n "${SRC:-}" ] && pactl set-source-volume "$SRC" 100% >/dev/null 2>&1

# The speaker's mic ships at 33%.
[ -n "${SPK_CARD:-}" ] && amixer -c "$SPK_CARD" sset Mic 100% unmute >/dev/null 2>&1 \
    && echo "speaker mic: capture at 100%"

# Echo cancellation, in PulseAudio rather than the browser.
#
# The speaker and the microphone are two SEPARATE USB devices, so the browser's
# AEC has no shared clock to correlate and cannot cancel anything — the robot
# hears itself and interrupts itself. module-echo-cancel sees both the sink and
# the source, so it can. Barge-in depends on this being loaded.
if ! pactl list short modules 2>/dev/null | grep -q echo-cancel; then
    if [ -n "${SRC:-}" ] && [ -n "${SINK:-}" ]; then
        # adjust_time=1 / adjust_threshold=1 matter as much as the canceller
        # itself. The Brio and the speaker are separate USB devices with
        # INDEPENDENT clocks, and AEC only works while playback and capture stay
        # aligned. At the default 10s resync interval the two drift apart and
        # cancellation collapses after roughly thirty seconds — the robot starts
        # transcribing its own voice again. Resyncing every second tracks it.
        pactl load-module module-echo-cancel \
            source_master="$SRC" sink_master="$SINK" \
            source_name=gerdoo_aec_source sink_name=gerdoo_aec_sink \
            aec_method=webrtc adjust_time=1 adjust_threshold=1 >/dev/null 2>&1 \
            && echo "echo cancellation: loaded" \
            || echo "echo cancellation: FAILED to load" >&2
        sleep 1
    fi
else
    echo "echo cancellation: already loaded"
fi

# module-stream-restore remembers which device each application used last and
# silently OVERRIDES the defaults for it. Firefox therefore stayed pinned to the
# raw microphone and raw sink, so the echo canceller was never in its path and
# the robot transcribed its own speech back as user input, verbatim. Unload it
# so applications follow the defaults set below.
if pactl list short modules 2>/dev/null | grep -q module-stream-restore; then
    pactl unload-module module-stream-restore >/dev/null 2>&1 \
        && echo "stream-restore: unloaded (apps now follow the defaults)"
fi

# Everything must go through the cancelled devices, both directions — the
# canceller can only subtract what it knows was played.
if pactl list short sources 2>/dev/null | grep -q gerdoo_aec_source; then
    pactl set-default-source gerdoo_aec_source && echo "default source: gerdoo_aec_source (AEC)"
    pactl set-default-sink   gerdoo_aec_sink   && echo "default sink:   gerdoo_aec_sink (AEC)"

    # Anything already streaming keeps its old device until moved, so drag any
    # live streams across too. Matters when this runs while a call is up.
    # cut, not awk: awk's $1 gets eaten by the shell here.
    pactl list short source-outputs 2>/dev/null | cut -f1 | while read -r so; do
        [ -n "$so" ] && pactl move-source-output "$so" gerdoo_aec_source >/dev/null 2>&1
    done
    pactl list short sink-inputs 2>/dev/null | cut -f1 | while read -r si; do
        [ -n "$si" ] && pactl move-sink-input "$si" gerdoo_aec_sink >/dev/null 2>&1
    done
else
    echo "AEC devices missing — falling back to the raw devices" >&2
    [ -n "${SRC:-}" ] && pactl set-default-source "$SRC" && echo "default source: $SRC"
    [ -n "${SINK:-}" ] && pactl set-default-sink "$SINK" && echo "default sink: $SINK"
fi

exit 0
