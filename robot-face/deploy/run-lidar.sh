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

# --- shutdown ---------------------------------------------------------------
# The C1's motor holds its last commanded state. It does NOT free-run on USB
# power, and it does NOT stop just because the driver process died — kill the
# node uncleanly and the lidar keeps spinning until someone unplugs it.
#
# rplidar_node::stop() sends setMotorSpeed(0), but only if rclcpp gets to run
# its shutdown handler, which needs SIGINT — SIGTERM through `ros2 launch` is
# not reliably converted. So: SIGINT first, then verify by sending the raw
# STOP command ourselves once the port is free.
#
# RPLIDAR protocol: 0xA5 0x25 = STOP. On the C1 the motor cannot run
# independently of the scan command, so STOP spins it down.
stop_motor_directly() {
    [ -e "$DEV" ] || return 0
    python3 - "$DEV" <<'PY' 2>/dev/null || true
import sys, time
try:
    with open(sys.argv[1], "wb", buffering=0) as f:
        f.write(b"\xA5\x25")   # STOP
        f.flush()
    time.sleep(0.1)
except OSError:
    pass
PY
}

shutdown() {
    echo "stopping — SIGINT to driver so it can spin the motor down"
    kill -INT $LIDAR_PID 2>/dev/null
    kill -INT ${BRIDGE_PID:-} 2>/dev/null

    # Give rclcpp a moment to run its shutdown and release the port.
    for _ in $(seq 1 20); do
        kill -0 $LIDAR_PID 2>/dev/null || break
        sleep 0.25
    done
    kill -TERM $LIDAR_PID ${BRIDGE_PID:-} 2>/dev/null
    wait 2>/dev/null

    # Belt and braces: whatever happened above, make sure the motor is told to
    # stop. Cheap, idempotent, and the difference between silence and a lidar
    # spinning all night.
    stop_motor_directly
    echo "motor stop command sent"
}

trap shutdown TERM INT

# If either child dies, bring the unit down so systemd reports it rather than
# leaving a half-running lidar — and so the motor still gets stopped.
wait -n $LIDAR_PID ${BRIDGE_PID:-$LIDAR_PID}
echo "a child exited — shutting down"
shutdown
