# Gerdoo

A robot built on an **NVIDIA Jetson Orin Nano** (planning, vision, AI) with a **Teensy 4.1** co-processor (real-time motor, servo and sensor control), talking over ROS 2 Humble.

Currently migrating from a legacy Arduino Nano build to the Teensy.

## Where things are

| Path | |
|---|---|
| [`inventory.md`](inventory.md) | **The wiring reference.** Every part, datasheet-backed, with voltage/logic compatibility and the power architecture. Start here |
| [`ACTION-PLAN.md`](ACTION-PLAN.md) | Numbered tasks with dated, measurable pass conditions |
| [`logs/`](logs/README.md) | One file per problem or design decision — evidence, wrong turns, root cause, fix, verification |
| [`teensy_bringup/`](teensy_bringup/) | Minimal health-check firmware + `health_check.py` |
| [`teensy_microros/`](teensy_microros/) | micro-ROS node — Dual Serial, console preserved |
| [`robot-face/`](robot-face/) | Kiosk face on the robot's screen + LAN control panel (mood, camera stream, live LiDAR view) |
| `PINOUT.md` | ⚠️ **Stale.** The legacy Arduino Nano build. Do not wire from it |
| `motor_controller/`, `encoder_test/`, … | Legacy Nano sketches, kept for reference |

## Architecture

```
Jetson Orin Nano ── ROS 2 Humble ── SLAM, navigation, vision, AI
   │
   ├── USB ── RPLIDAR C1          (own MCU — no co-processor needed)
   ├── USB ── Logitech Brio 500   (control-panel stream)
   ├── HDMI ─ 5.5" AMOLED panel   (kiosk face)
   └── USB ── Teensy 4.1  ── micro-ROS `/teensy_node`
                  │
                  ├── motors via BTS7960, 20 kHz PWM
                  ├── wheel encoders (hardware quadrature)
                  ├── servos via PCA9685 / STS3215
                  └── ultrasonics, lights, weather
```

**The split rule: the MCU is there for timing determinism, not to offload CPU.**
Linux can pause a process for tens of milliseconds with no warning. That is fine for
planning and fatal for a 20 kHz PWM waveform or an encoder edge. Anything that must
happen at an exact microsecond lives on the Teensy; everything else lives on the
Jetson. A USB peripheral with its own microcontroller — like the lidar — has already
delegated, so putting the Teensy in front of it only adds a middleman.

## Conventions

- **Never hardcode `/dev/ttyACM<N>`, `/dev/ttyUSB<N>` or `/dev/video<N>`.** They move on
  re-enumeration. Use the `/dev/serial/by-id/` and `/dev/v4l/by-id/` paths listed in
  `inventory.md` — they are keyed on each device's serial number.
- **Measure before connecting.** The Teensy 4.1 is not 5 V tolerant; its ESD clamp is
  3.6 V. Every pin that reaches it gets a meter on it first.
- **Log every problem**, including the wrong turns. A wrong guess documented once is a
  wrong guess not repeated.
- Runtime config (`robot-face/config.json`, `state.json`) is device-specific, holds
  secrets, and is **never committed**.

## Status

Teensy healthy on micro-ROS · lidar publishing `/scan` at 10 Hz · control panel live.
Power tree and wiring still ahead — see `ACTION-PLAN.md`.

## License

[MIT](LICENSE) — hardware docs, firmware and software all under it.
