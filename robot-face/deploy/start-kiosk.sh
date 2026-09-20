#!/usr/bin/env bash
# Launch the kiosk browser so the video player can float above it.
#
# NOT --kiosk. --kiosk sets _NET_WM_STATE_FULLSCREEN, and xfwm4 stacks
# fullscreen windows above _NET_WM_STATE_ABOVE. With mpv sized to leave a strip
# for the toolbar (video-player.service), that put the face ON TOP of the video
# and made the Wake button unreachable over playing music — the one case it
# exists for. See log 025.
#
# Chrome is hidden by chrome/userChrome.css in the profile instead, and the
# window is undecorated by declaring it a splash (below).
set -u
export DISPLAY="${DISPLAY:-:0}"
PROFILE="${PROFILE:-$HOME/.robotface-ff}"
URL="${URL:-http://localhost:8080/}"

# Screen size, read rather than hard-coded — rotate-display.sh turns the panel.
SCREEN_W=$(xdotool getdisplaygeometry 2>/dev/null | cut -d' ' -f1); SCREEN_W=${SCREEN_W:-1920}
SCREEN_H=$(xdotool getdisplaygeometry 2>/dev/null | cut -d' ' -f2); SCREEN_H=${SCREEN_H:-1080}

# Touchscreen + GPU on Tegra, same as the old launcher.
export MOZ_USE_XINPUT2=1 MOZ_X11_EGL=1 MOZ_WEBRENDER=1

# plank is a dock: it floats above the browser and sits exactly where the Wake
# button is, swallowing taps meant for it. A robot kiosk has no use for a dock.
pkill -x plank 2>/dev/null

/usr/lib/firefox/firefox --profile "$PROFILE" --new-window "$URL" &
FF=$!

# Wait for the window. Firefox accepts no geometry flag on X11, so everything
# below has to happen after it maps.
W=""
for _ in $(seq 1 40); do
    W=$(xdotool search --class firefox 2>/dev/null | tail -1)
    [ -n "$W" ] && break
    sleep 1
done
if [ -z "$W" ]; then
    echo "kiosk: firefox window never appeared" >&2
    wait "$FF"
    exit 1
fi

# Undecorate by declaring the window a SPLASH.
#
# _MOTIF_WM_HINTS with decorations=0 was tried first and is NOT reliable here:
# xfwm4 honoured it on some launches and drew a titlebar anyway on others,
# leaving "Robot Face — Mozilla Firefox" across the top of the robot's face.
# Shifting the window up to hide the frame did not work either — xdotool's move
# was simply ignored.
#
# _NET_WM_WINDOW_TYPE_SPLASH is undecorated by definition and still sits in the
# WM's NORMAL stacking layer, which is the point: the video player's
# _NET_WM_STATE_ABOVE has to keep winning over it. A dock or fullscreen type
# would reopen the very stacking fight this arrangement exists to end.
#
# The type is read when the window is mapped, so it is remapped once.
xprop -id "$W" -f _NET_WM_WINDOW_TYPE 32a \
    -set _NET_WM_WINDOW_TYPE _NET_WM_WINDOW_TYPE_SPLASH 2>/dev/null
xdotool windowunmap "$W" 2>/dev/null
sleep 1
xdotool windowmap "$W" 2>/dev/null
sleep 2
xdotool windowmove "$W" 0 0 2>/dev/null
xdotool windowsize "$W" "$SCREEN_W" "$SCREEN_H" 2>/dev/null

# Report what actually happened, so a wrong result shows up in the unit's log
# instead of only on the robot's face.
sleep 1
echo "kiosk: window $W -> $(xwininfo -id "$W" 2>/dev/null \
    | awk '/Absolute upper-left Y/ {y=$NF} /^  Width/ {w=$NF} /^  Height/ {h=$NF} END {print w"x"h" at y="y}')"

wait "$FF"
