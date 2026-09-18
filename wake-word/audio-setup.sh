#!/usr/bin/env bash
# Put the robot's audio into a known state.
#
# Microphone AND speaker are one device: the reSpeaker Flex XVF3800 (USB,
# 16 kHz). The XVF3800 does echo cancellation in hardware, against the exact
# samples it is playing, on one clock. That replaces the old Brio + USB speaker
# pair, whose independent clocks made software AEC (PulseAudio
# module-echo-cancel) drift apart within ~30 s of every call.
#
# Everything here resolves devices BY NAME. Card indices move on replug — the
# same trap as /dev/ttyACM* and PortAudio indices.
set -u
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

XVF_NAME="${XVF_NAME:-XVF3800}"
# 85%, deliberately not 100%. At full output the robot hears itself through the
# room loudly enough that the XVF3800's canceller cannot subtract it all, and the
# agent starts transcribing its own voice. The other end of the scale is just as
# wrong: the shipped 67% is -20 dB and sounds broken. Change this only with a
# real call to judge it by.
SPK_LEVEL="${SPK_LEVEL:-85%}"
MIC_SOURCE=gerdoo_mic

# ALSA mixer. There are TWO playback controls: PCM,0 (left/right) and PCM,1
# (a mono master). PCM,1 ships at 67% = -20 dB and quietly caps everything
# else, so the speaker sounds weak even with PCM,0 and PulseAudio at 100%.
XVF_CARD=$(awk -v want="$XVF_NAME" 'index($0, want) && $1 ~ /^[0-9]+$/ {print $1; exit}' /proc/asound/cards)
if [ -n "${XVF_CARD:-}" ]; then
    amixer -c "$XVF_CARD" sset PCM,0 "$SPK_LEVEL" unmute >/dev/null 2>&1
    amixer -c "$XVF_CARD" sset PCM,1 "$SPK_LEVEL" unmute >/dev/null 2>&1
    amixer -c "$XVF_CARD" sset Headset 100% unmute >/dev/null 2>&1
    echo "xvf3800: card $XVF_CARD, speaker at $SPK_LEVEL"
else
    echo "xvf3800: card matching '$XVF_NAME' NOT FOUND" >&2
fi

# PulseAudio can take a moment to publish a freshly plugged card.
for _ in 1 2 3 4 5; do
    MASTER=$(pactl list short sources 2>/dev/null | awk -v want="$XVF_NAME" 'index($2, want) && !/monitor/ {print $2; exit}')
    [ -n "${MASTER:-}" ] && break
    sleep 1
done
SINK=$(pactl list short sinks 2>/dev/null | awk -v want="$XVF_NAME" 'index($2, want) && !/monitor/ {print $2; exit}')

# The 6-channel firmware delivers:
#   ch0  processed: AEC + beamforming + noise suppression + AGC  <- we use this
#   ch1  ASR beam (auto-selected), same processing chain, lower gain
#   ch2-5  the four raw microphones, NOT echo-cancelled
# Any application that opens the 6-channel source and downmixes it (Firefox
# does) blends the raw mics back in and undoes the echo cancellation. So expose
# channel 0 alone as a mono source and make that the only thing apps see.
if ! pactl list short sources 2>/dev/null | grep -q "$MIC_SOURCE"; then
    if [ -n "${MASTER:-}" ]; then
        pactl load-module module-remap-source master="$MASTER" \
            source_name="$MIC_SOURCE" \
            source_properties=device.description=Gerdoo_mic_XVF3800 \
            channels=1 master_channel_map=front-left channel_map=mono remix=no \
            >/dev/null 2>&1 \
            && echo "mic: $MIC_SOURCE = XVF3800 channel 0 (processed)" \
            || echo "mic: FAILED to create $MIC_SOURCE" >&2
    fi
else
    echo "mic: $MIC_SOURCE already present"
fi

# The software canceller from the Brio era must not come back: stacked on the
# XVF3800 it would fight the hardware AEC.
pactl list short modules 2>/dev/null | awk '/module-echo-cancel/ {print $1}' | while read -r m; do
    pactl unload-module "$m" >/dev/null 2>&1 && echo "echo-cancel: unloaded (hardware AEC now)"
done

# module-stream-restore remembers which device each application used last and
# silently OVERRIDES the defaults for it — Firefox stayed pinned to a raw
# device and the robot transcribed its own speech back. Unload it so
# applications follow the defaults set below.
if pactl list short modules 2>/dev/null | grep -q module-stream-restore; then
    pactl unload-module module-stream-restore >/dev/null 2>&1 \
        && echo "stream-restore: unloaded (apps now follow the defaults)"
fi

if pactl list short sources 2>/dev/null | grep -q "$MIC_SOURCE" && [ -n "${SINK:-}" ]; then
    pactl set-default-source "$MIC_SOURCE" && echo "default source: $MIC_SOURCE"
    pactl set-default-sink "$SINK" && echo "default sink:   $SINK"
    pactl set-sink-volume "$SINK" 100% >/dev/null 2>&1

    # Anything already streaming keeps its old device until moved. Matters when
    # this runs while a call is up. cut, not awk: awk's $1 gets eaten here.
    pactl list short source-outputs 2>/dev/null | cut -f1 | while read -r so; do
        [ -n "$so" ] && pactl move-source-output "$so" "$MIC_SOURCE" >/dev/null 2>&1
    done
    pactl list short sink-inputs 2>/dev/null | cut -f1 | while read -r si; do
        [ -n "$si" ] && pactl move-sink-input "$si" "$SINK" >/dev/null 2>&1
    done
else
    echo "XVF3800 not ready — defaults left unchanged" >&2
fi

exit 0
