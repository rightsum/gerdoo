#!/bin/bash
# Start the RPLIDAR C1 driver plus the /scan -> control-panel bridge.
#
# On-demand only: rplidar.service is installed but NOT enabled, so the motor
# spins solely while the panel asks for it.
#
# Both processes run under one unit. When systemd stops the unit its default
# KillMode=control-group reaps the whole cgroup, so the driver and the bridge
# always go together — no orphan holding /dev/ttyUSB0.

# ROS setup scripts are not `set -u` clean (setup.bash reads
# AMENT_TRACE_SETUP_FILES unconditionally), so sourcing happens before any
# strictness is enabled. See logs/007.
source /opt/ros/humble/setup.bash
[ -f "$HOME/ros2_ws/install/local_setup.bash" ] && source "$HOME/ros2_ws/install/local_setup.bash"

set -u

# Keyed on the adapter's own serial number: /dev/ttyUSB0 moves on
# re-enumeration, and the launch file's default points at exactly that.
DEV="${LIDAR_DEV:-/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_ec8fc9bc95d5ef11afac704b49d2c684-if00-port0}"
BRIDGE="$HOME/robot-face/scan_bridge.py"

if [ ! -e "$DEV" ]; then
    echo "ERROR: lidar not found at $DEV" >&2
    echo "  Plugged in? Check: ls /dev/serial/by-id/" >&2
    exit 1
fi

echo "starting rplidar_ros on $DEV"
ros2 launch rplidar_ros rplidar_c1_launch.py serial_port:="$DEV" &
LIDAR_PID=$!

# Give the driver a moment to come up before the bridge starts looking for
# /scan, purely to keep the logs clean.
sleep 3

if [ -f "$BRIDGE" ]; then
    echo "starting scan bridge"
    python3 "$BRIDGE" &
    BRIDGE_PID=$!
else
    echo "WARNING: $BRIDGE missing — lidar will run but the panel shows no scan" >&2
    BRIDGE_PID=""
fi

# Forward termination to both children so `systemctl --user stop` is clean and
# the lidar motor actually spins down.
trap 'kill $LIDAR_PID $BRIDGE_PID 2>/dev/null' TERM INT

# If either child dies, bring the unit down so systemd reports it rather than
# leaving a half-running lidar.
wait -n $LIDAR_PID ${BRIDGE_PID:-$LIDAR_PID}
echo "a child exited — shutting down"
kill $LIDAR_PID $BRIDGE_PID 2>/dev/null
wait
