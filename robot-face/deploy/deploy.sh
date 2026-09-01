#!/usr/bin/env bash
# Deploy Robot Face to the Jetson and (re)install its user service + kiosk autostart.
# No root required. Run from the project root on your Mac:  ./deploy/deploy.sh
set -euo pipefail

# Where the robot lives. Personal — set it one of two ways, both gitignored:
#   1. ROBOT=user@192.168.x.x ./deploy/deploy.sh
#   2. deploy/deploy.env (gitignored) containing:  ROBOT=user@192.168.x.x
#      and optionally DEST=/home/user/robot-face and FACE_PORT=8080
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$HERE/deploy/deploy.env" ] && . "$HERE/deploy/deploy.env"

if [ -z "${ROBOT:-}" ]; then
  echo "ERROR: ROBOT is not set — who am I deploying to?" >&2
  echo "  ROBOT=user@robot-ip ./deploy/deploy.sh" >&2
  echo "  or put it in deploy/deploy.env (gitignored). See deploy.env.example." >&2
  exit 1
fi
DEST="${DEST:-/home/${ROBOT%%@*}/robot-face}"
FACE_PORT="${FACE_PORT:-8080}"

echo "==> Syncing code to $ROBOT:$DEST"
rsync -az --delete \
  --exclude '.git' --exclude '__pycache__' \
  --exclude 'config.json' --exclude 'state.json' \
  --exclude 'models' \
  "$HERE"/ "$ROBOT:$DEST"/

echo "==> Installing + starting user service (systemctl --user, no sudo)"
ssh "$ROBOT" "export XDG_RUNTIME_DIR=/run/user/\$(id -u); \
  mkdir -p ~/.config/systemd/user; \
  cp $DEST/deploy/robot-face.service ~/.config/systemd/user/robot-face.service; \
  systemctl --user daemon-reload; \
  systemctl --user enable --now robot-face; \
  systemctl --user restart robot-face; \
  sleep 2; systemctl --user is-active robot-face"

# Installed but deliberately NOT enabled: the lidar motor should spin only when
# the control panel asks for it, never at boot.
echo "==> Installing on-demand lidar unit (installed, not enabled)"
ssh "$ROBOT" "export XDG_RUNTIME_DIR=/run/user/\$(id -u); \
  chmod +x $DEST/deploy/run-lidar.sh $DEST/scan_bridge.py; \
  cp $DEST/deploy/rplidar.service ~/.config/systemd/user/rplidar.service; \
  systemctl --user daemon-reload; \
  echo -n 'rplidar unit: '; systemctl --user list-unit-files rplidar.service --no-legend"

# Also installed but not enabled. Runs from ~/gesture-venv (MediaPipe needs
# numpy 2.2 / cv2 5.0, which would break the system cv2 4.8 and ROS).
echo "==> Installing on-demand gesture unit (installed, not enabled)"
ssh "$ROBOT" "export XDG_RUNTIME_DIR=/run/user/\$(id -u); \
  cp $DEST/deploy/gesture.service ~/.config/systemd/user/gesture.service; \
  systemctl --user daemon-reload; \
  echo -n 'gesture unit: '; systemctl --user list-unit-files gesture.service --no-legend; \
  test -x ~/gesture-venv/bin/python && echo 'gesture venv: OK' || echo 'gesture venv: MISSING — see logs/010'; \
  test -f $DEST/models/gesture_recognizer.task && echo 'gesture model: OK' || echo 'gesture model: MISSING — see logs/010'"

echo "==> Installing kiosk autostart (replaces the old placetory autostart)"
ssh "$ROBOT" "cp $DEST/deploy/robot-face-kiosk.desktop ~/.config/autostart/robot-face-kiosk.desktop; \
  rm -f ~/.config/autostart/firefox-fullscreen.desktop"

echo "==> Done."
echo "Face:    http://localhost:$FACE_PORT/                (robot, kiosk)"
echo "Control: http://${ROBOT##*@}:$FACE_PORT/control    (from your desktop)"
