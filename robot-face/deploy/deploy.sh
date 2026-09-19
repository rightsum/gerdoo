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
echo "==> Installing on-demand face-track unit (installed, not enabled)"
ssh "$ROBOT" "export XDG_RUNTIME_DIR=/run/user/\$(id -u); \
  cp $DEST/deploy/face-track.service ~/.config/systemd/user/face-track.service; \
  systemctl --user daemon-reload; \
  echo -n 'face-track unit: '; systemctl --user list-unit-files face-track.service --no-legend; \
  test -x ~/gesture-venv/bin/python && echo 'face-track venv: OK' || echo 'face-track venv: MISSING — see logs/010'; \
  test -f $DEST/models/blaze_face_short_range.tflite && echo 'face-track model: OK' || echo 'face-track model: MISSING — see logs/010'"

# Enabled at boot, unlike lidar and face-track above: the control panel talks
# to mpv over its IPC socket, so mpv must already be up and listening whenever
# a video is requested, not started on demand.
#
# mpv itself is installed by hand (see README), not by this script, so on a
# robot that doesn't have it yet the unit will enable but sit restarting.
# That check must not abort the deploy — a run for an unrelated change would
# otherwise skip kiosk-autostart and the final banner just because mpv isn't
# installed yet.
echo "==> Installing + starting video-player unit (systemctl --user, no sudo)"
ssh "$ROBOT" "export XDG_RUNTIME_DIR=/run/user/\$(id -u); \
  cp $DEST/deploy/video-player.service ~/.config/systemd/user/video-player.service; \
  systemctl --user daemon-reload; \
  systemctl --user enable --now video-player; \
  sleep 2; systemctl --user is-active video-player || echo 'video-player: not active — install mpv on the robot first'"

# The battery bridge writes /tmp/battery_status.json, which the panel's battery
# bars read. It had never once started on its own: its unit ordered itself
# After=micro-ros-agent.service, which was itself ordered After=default.target
# while being WantedBy it — so systemd found an ordering cycle and deleted this
# service's start job. Silently: no failure, no journal entry, blank bars.
# The unit shipped here has that edge removed.
echo "==> Installing + starting battery-bridge unit (systemctl --user, no sudo)"
ssh "$ROBOT" "export XDG_RUNTIME_DIR=/run/user/\$(id -u); \
  cp $DEST/deploy/battery-bridge.service ~/.config/systemd/user/battery-bridge.service; \
  systemctl --user daemon-reload; \
  systemctl --user reenable battery-bridge >/dev/null 2>&1; \
  systemctl --user restart battery-bridge; \
  sleep 2; systemctl --user is-active battery-bridge || echo 'battery-bridge: not active'"

echo "==> Installing kiosk autostart (replaces the old placetory autostart)"
ssh "$ROBOT" "cp $DEST/deploy/robot-face-kiosk.desktop ~/.config/autostart/robot-face-kiosk.desktop; \
  rm -f ~/.config/autostart/firefox-fullscreen.desktop"

echo "==> Done."
echo "Face:    http://localhost:$FACE_PORT/                (robot, kiosk)"
echo "Control: http://${ROBOT##*@}:$FACE_PORT/control    (from your desktop)"
