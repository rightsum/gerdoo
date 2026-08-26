#!/usr/bin/env python3
"""
Battery bridge — collects both battery voltages and writes to JSON for the Flask app.

- Main battery: subscribed from ROS 2 topic /teensy/battery_main (published by Teensy)
- UPS battery:  read from INA219 on I2C bus 7, address 0x41 (Waveshare UPS Module C)

Writes /tmp/battery_status.json every 3 seconds.

IMPORTANT: Only reads INA219 register 0x02 (bus voltage). Reading other
registers on bus 7 caused a system reboot in testing — keep I2C access
minimal.
"""
import json
import os
import time
import threading

STATUS_FILE = "/tmp/battery_status.json"
UPDATE_INTERVAL = 3  # seconds

# --- UPS battery via INA219 (I2C bus 7, address 0x41) ---

def read_ups_voltage():
    """Read UPS battery voltage from INA219. Returns voltage in V or None."""
    try:
        import smbus
        import struct
        bus = smbus.SMBus(7)
        # Read ONLY register 0x02 (bus voltage). Do NOT read other registers.
        raw = bus.read_word_data(0x41, 0x02)
        bus.close()
        # INA219 is big-endian; smbus returns little-endian
        val = struct.unpack(">H", struct.pack("<H", raw))[0]
        # Bits [15:3] = voltage in 4mV steps
        voltage = (val >> 3) * 0.004
        return voltage
    except Exception as e:
        return None

# --- Main battery via ROS 2 ---

_main_battery_voltage = None
_main_battery_lock = threading.Lock()

def ros_loop():
    """Subscribe to /teensy/battery_main and cache the voltage."""
    global _main_battery_voltage
    try:
        import rclpy
        from rclpy.node import Node
        from std_msgs.msg import Float32

        rclpy.init()
        node = rclpy.create_node("battery_listener")
        node.create_subscription(Float32, "teensy/battery_main",
                                  lambda msg: setattr_main(msg.data), 10)
        rclpy.spin(node)
    except Exception as e:
        print(f"ROS loop failed: {e}")

def setattr_main(voltage):
    global _main_battery_voltage
    with _main_battery_lock:
        _main_battery_voltage = voltage

def get_main_voltage():
    with _main_battery_lock:
        return _main_battery_voltage

# --- Voltage to percentage ---

def voltage_to_percent_3s(v):
    """3S Li-ion: 12.6V=100%, 11.1V=~50%, 9.0V=0%"""
    if v is None:
        return None
    if v >= 12.6:
        return 100
    if v <= 9.0:
        return 0
    return round((v - 9.0) / (12.6 - 9.0) * 100)

# --- Main loop ---

def main():
    # Start ROS subscriber in a background thread
    ros_thread = threading.Thread(target=ros_loop, daemon=True)
    ros_thread.start()

    while True:
        main_v = get_main_voltage()
        ups_v = read_ups_voltage()

        status = {
            "main_battery": {
                "voltage": round(main_v, 2) if main_v is not None else None,
                "percent": voltage_to_percent_3s(main_v),
            },
            "jetson_battery": {
                "voltage": round(ups_v, 2) if ups_v is not None else None,
                "percent": voltage_to_percent_3s(ups_v),
            },
            "updated": time.time(),
        }

        try:
            tmp = STATUS_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(status, f)
            os.replace(tmp, STATUS_FILE)
        except Exception as e:
            print(f"Failed to write status: {e}")

        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    main()