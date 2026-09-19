#!/usr/bin/env bash
# Launch the kiosk browser so the video player can float above it.
#
# NOT --kiosk. --kiosk sets _NET_WM_STATE_FULLSCREEN, and xfwm4 stacks
# fullscreen windows above _NET_WM_STATE_ABOVE. With mpv sized to leave a strip
# for the toolbar (video-player.service), that put the face ON TOP of the video
# and made the Wake button unreachable over playing music — the one case it
# exists for. See log 025.
#
# A maximized, undecorated window sits in the WM's normal layer instead, so mpv
# floats over it and the strip stays visible. Chrome is hidden by
# chrome/userChrome.css in the profile rather than by --kiosk.
set -u
export DISPLAY="${DISPLAY:-:0}"
PROFILE="${PROFILE:-$HOME/.robotface-ff}"
URL="${URL:-http://localhost:8080/}"

# Screen size, read rather than hard-coded — rotate-display.sh turns the panel,
# and the video player's --geometry is derived from the same numbers.
SCREEN_W=$(xdotool getdisplaygeometry 2>/dev/null | cut -d" " -f1); SCREEN_W=${SCREEN_W:-1920}
SCREEN_H=$(xdotool getdisplaygeometry 2>/dev/null | cut -d" " -f2); SCREEN_H=${SCREEN_H:-1080}

# Touchscreen + GPU on Tegra, same as the old launcher.
export MOZ_USE_XINPUT2=1 MOZ_X11_EGL=1 MOZ_WEBRENDER=1

# plank is a dock: it floats above the browser and sits exactly where the Wake
# button is, swallowing taps meant for it. A robot kiosk has no use for a dock.
pkill -x plank 2>/dev/null

/usr/lib/firefox/firefox --profile "$PROFILE" --new-window "$URL" &
FF=$!

# Wait for the window, then strip decorations and fill the screen. Firefox does
# not accept a geometry flag on X11, so this is done after mapping.
for _ in $(seq 1 40); do
    W=$(xdotool search --class firefox 2>/dev/null | tail -1)
    [ -n "${W:-}" ] && break
    sleep 1
done
if [ -z "${W:-}" ]; then
    echo "kiosk: firefox window never appeared" >&2
    wait $FF
    exit 1
fi

# Ask for no decorations: MWM_HINTS_DECORATIONS with decorations = 0. Applied at
# map time, so the window is remapped once for it to take.
xprop -id "$W" -f _MOTIF_WM_HINTS 32c -set _MOTIF_WM_HINTS "2, 0, 0, 0, 0" 2>/dev/null
xdotool windowunmap "$W" 2>/dev/null; sleep 1; xdotool windowmap "$W" 2>/dev/null; sleep 2

# ...and do not trust it. xfwm4 honoured the hint on some launches and drew a
# titlebar anyway on others, which pushes the page down and steals a strip of
# the screen. Rather than fight it, measure whatever frame ended up there and
# push the window up by exactly that much, so the PAGE starts at y=0 and any
# leftover titlebar sits off-screen above it.
xdotool windowmove "$W" 0 0 2>/dev/null
xdotool windowsize "$W" "$SCREEN_W" "$SCREEN_H" 2>/dev/null
sleep 1
OFF=$(xwininfo -id "$W" 2>/dev/null | awk '/Absolute upper-left Y/ {print $NF}')
if [ -n "${OFF:-}" ] && [ "$OFF" -gt 0 ] 2>/dev/null; then
    xdotool windowmove "$W" 0 "-$OFF" 2>/dev/null
    xdotool windowsize "$W" "$SCREEN_W" "$SCREEN_H" 2>/dev/null
fi

wait $FF
