#!/usr/bin/env bash
# Deploy Robot Face to the Jetson and (re)install its user service + kiosk autostart.
# No root required. Run from the project root on your Mac:  ./deploy/deploy.sh
set -euo pipefail

ROBOT="${ROBOT:-user@<robot-ip>}"
DEST="/home/jarvis/robot-face"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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
echo "Face:    http://localhost:8080/                (robot, kiosk)"
echo "Control: http://<robot-ip>:8080/control    (from your desktop)"
