#!/bin/bash
# micro-ROS agent launcher for the Teensy 4.1.
#
# Two things this handles that a bare ExecStart cannot:
#
# 1. The Teensy may not be enumerated yet when the user session starts, and it
#    disappears for several seconds on every reflash. So wait for the device
#    rather than failing instantly and burning systemd restart budget.
#
# 2. `ros2 run micro_ros_agent ...` is a PYTHON WRAPPER. If it is the unit's
#    main process, the real agent binary becomes a child — and killing the
#    wrapper orphans a process still holding the serial port. That cost real
#    debugging time (see logs/007). Exec the binary directly so systemd's main
#    PID *is* the agent.

set -u

# Keyed on this board's serial number, not a glob: once the arm Teensy is added
# a glob would race between two boards. Update if the board is replaced.
DEV="${TEENSY_DEV:-/dev/serial/by-id/usb-Teensyduino_Dual_Serial_19627940-if02}"
BAUD="${TEENSY_BAUD:-115200}"
WAIT_SECS="${TEENSY_WAIT:-60}"

ROS_SETUP=/opt/ros/humble/setup.bash
WS_SETUP="$HOME/ros2_ws/install/local_setup.bash"
AGENT="$HOME/ros2_ws/install/micro_ros_agent/lib/micro_ros_agent/micro_ros_agent"

for i in $(seq 1 "$WAIT_SECS"); do
    [ -e "$DEV" ] && break
    [ "$i" = 1 ] && echo "waiting for $DEV ..."
    sleep 1
done

if [ ! -e "$DEV" ]; then
    echo "ERROR: $DEV did not appear after ${WAIT_SECS}s." >&2
    echo "  Is the Teensy plugged in and in Dual Serial mode (lsusb: 16c0:048b)?" >&2
    exit 1
fi

# ROS setup scripts are not `set -u` clean — /opt/ros/humble/setup.bash reads
# AMENT_TRACE_SETUP_FILES unconditionally and aborts the script under `set -u`.
# Drop the check just for the sourcing, then restore it.
set +u
# shellcheck disable=SC1090
source "$ROS_SETUP"
# shellcheck disable=SC1090
[ -f "$WS_SETUP" ] && source "$WS_SETUP"
set -u

if [ ! -x "$AGENT" ]; then
    echo "ERROR: agent binary not found at $AGENT" >&2
    echo "  Build it: cd ~/ros2_ws && colcon build --packages-up-to micro_ros_agent" >&2
    exit 1
fi

echo "starting micro-ROS agent on $DEV @ ${BAUD}"
exec "$AGENT" serial --dev "$DEV" -b "$BAUD"
