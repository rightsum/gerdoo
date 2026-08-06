#!/bin/bash
# Rotate the 5.5" panel to landscape and match the touchscreen to it.
#
# The panel is physically 1080x1920 (portrait). xrandr rotates the image, but
# the touchscreen knows nothing about that — without a matching calibration
# matrix, touches land 90 degrees off.
#
# WHY THIS EXISTS AS A SCRIPT:
# The previous version was a one-liner in the .desktop file that did
#
#     xinput set-prop 7 "libinput Calibration Matrix" ...
#
# xinput device IDs are assigned in enumeration order and are NOT stable.
# Plugging in a webcam shifted everything by one, so ID 7 became the Brio 500
# and the calibration silently went to a camera instead of the touchscreen —
# no error, just uncalibrated touch. See logs/011.
#
# Devices are therefore matched BY NAME here. Same rule as /dev/serial/by-id
# elsewhere in this project: never address hardware by a number the kernel
# hands out in arrival order.

OUTPUT="${DISPLAY_OUTPUT:-DP-1}"
ROTATION="${DISPLAY_ROTATION:-right}"

# 90° clockwise. Rows map touch (x,y,1) to display space.
MATRIX="${TOUCH_MATRIX:-0 1 0 -1 0 1 0 0 1}"

log() { echo "[rotate-display] $*"; }

# The X session may not be ready the instant autostart fires.
for _ in $(seq 1 15); do
    xrandr --query >/dev/null 2>&1 && break
    sleep 1
done

if ! xrandr --query >/dev/null 2>&1; then
    log "ERROR: no X display available"
    exit 1
fi

# --- rotate the image ------------------------------------------------------
if xrandr --query | grep -q "^${OUTPUT} connected"; then
    xrandr --output "$OUTPUT" --rotate "$ROTATION"
    log "rotated $OUTPUT to $ROTATION"
else
    log "WARNING: $OUTPUT is not connected — skipping rotation"
    xrandr --query | grep " connected" | sed 's/^/  available: /'
fi

# --- match the touchscreen -------------------------------------------------
# Match on name, case-insensitively. Most USB touch panels advertise
# "touchscreen" or "touch"; add patterns here if a new panel does not.
mapfile -t TOUCH_IDS < <(
    xinput list --short 2>/dev/null \
      | grep -iE "touch|ILITEK|eGalax|Goodix|silead" \
      | grep -oP 'id=\K[0-9]+'
)

if [ ${#TOUCH_IDS[@]} -eq 0 ]; then
    log "no touchscreen found in xinput — is the panel's TOUCH USB cable connected?"
    log "  (HDMI carries video only; touch is a separate USB lead on the driver board)"
    xinput list --short 2>/dev/null | sed 's/^/  /'
    exit 0        # not an error: video still works, and this must not fail boot
fi

for id in "${TOUCH_IDS[@]}"; do
    name=$(xinput list --name-only "$id" 2>/dev/null)
    # libinput and the legacy evdev driver spell the property differently, and
    # which one is in use depends on the X input driver. Try both; at least one
    # will apply, and the other simply fails.
    if xinput set-prop "$id" "libinput Calibration Matrix" $MATRIX 2>/dev/null; then
        log "calibrated '$name' (id=$id) via libinput"
    elif xinput set-prop "$id" "Coordinate Transformation Matrix" $MATRIX 2>/dev/null; then
        log "calibrated '$name' (id=$id) via Coordinate Transformation Matrix"
    else
        log "WARNING: could not set a calibration matrix on '$name' (id=$id)"
        xinput list-props "$id" 2>/dev/null | grep -i matrix | sed 's/^/    /'
    fi

    # Map the device to the rotated output too. This is what keeps touch
    # correct on a multi-monitor setup, and is harmless with one screen.
    xinput map-to-output "$id" "$OUTPUT" 2>/dev/null \
        && log "mapped '$name' to $OUTPUT"
done
