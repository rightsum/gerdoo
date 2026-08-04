#!/usr/bin/env python3
"""Bridge /scan into the robot-face control panel.

Runs INSIDE a ROS environment (launched by rplidar.service). Subscribes to
/scan, downsamples, and POSTs to the Flask app on localhost.

Why a separate process rather than rclpy inside app.py: the face app runs on
system Python with no ROS on its path, and it must be able to start when ROS
is not running at all. A one-way HTTP push keeps the face app ROS-free and
means a crash here cannot take the face down.

The lidar produces 721 points at 10 Hz. Pushing that raw would be ~7 KB * 10/s
per viewer for a canvas a few hundred pixels wide — far more resolution than
can be drawn. So it is downsampled to TARGET_POINTS and rate-limited.
"""
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import LaserScan

INGEST_URL = os.environ.get("ROBOT_FACE_INGEST", "http://127.0.0.1:8080/api/lidar/ingest")
TARGET_POINTS = int(os.environ.get("SCAN_POINTS", "360"))
PUBLISH_HZ = float(os.environ.get("SCAN_PUSH_HZ", "5"))


class ScanBridge(Node):
    def __init__(self):
        super().__init__("scan_bridge")
        # The lidar driver publishes BEST_EFFORT; a RELIABLE subscription would
        # silently never match it.
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.sub = self.create_subscription(LaserScan, "/scan", self.on_scan, qos)
        self.min_interval = 1.0 / PUBLISH_HZ if PUBLISH_HZ > 0 else 0.0
        self.last_push = 0.0
        self.pushed = 0
        self.failures = 0
        self.get_logger().info(
            f"bridging /scan -> {INGEST_URL} at {PUBLISH_HZ} Hz, {TARGET_POINTS} points"
        )

    def on_scan(self, msg: LaserScan):
        now = time.monotonic()
        if now - self.last_push < self.min_interval:
            return
        self.last_push = now

        n = len(msg.ranges)
        if n == 0:
            return
        step = max(1, n // TARGET_POINTS)

        pts = []
        for i in range(0, n, step):
            r = msg.ranges[i]
            # inf/NaN mean "no return" — send null so the client can skip the
            # point instead of drawing a spurious wall at range_max.
            if r is None or math.isinf(r) or math.isnan(r) or r <= 0.0:
                pts.append(None)
            else:
                pts.append(round(float(r), 3))

        payload = {
            "angle_min": round(float(msg.angle_min), 6),
            "angle_increment": round(float(msg.angle_increment) * step, 8),
            "range_min": round(float(msg.range_min), 3),
            "range_max": round(float(msg.range_max), 3),
            "count": len(pts),
            "stamp": time.time(),
            "ranges": pts,
        }
        self.push(payload)

    def push(self, payload):
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            INGEST_URL, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=1.5):
                pass
            self.pushed += 1
            if self.failures:
                self.get_logger().info("ingest recovered")
                self.failures = 0
        except (urllib.error.URLError, OSError) as exc:
            self.failures += 1
            # The face app may be restarting, or simply not running. Log the
            # first failure and then every ~10s, not every dropped frame.
            if self.failures == 1 or self.failures % int(max(PUBLISH_HZ * 10, 1)) == 0:
                self.get_logger().warn(f"ingest failed ({self.failures}x): {exc}")


def main():
    rclpy.init(args=sys.argv)
    node = ScanBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
