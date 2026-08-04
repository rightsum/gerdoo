# 004 — RPLIDAR C1 bring-up on Jetson USB

| | |
|---|---|
| **Date** | 2026-08-04 |
| **Type** | Bring-up — first light |
| **Status** | ✅ Working — publishing `/scan` at 10.008 Hz |
| **Duration** | ~10 min, no code written |
| **Validates** | The lidar-to-Jetson decision in [log 002](002-2026-08-04-usb-topology-and-peripheral-split.md) |
| **Hardware** | RPLIDAR C1 (S/N `CDA9E18DC2E699D7C89792F4370A416F`) → CP2102N → Jetson USB |

---

## What was done

Plugged the C1's USB adapter into a Jetson port and launched the driver already sitting in the workspace. **No firmware written, no wiring, no measurement.**

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 launch rplidar_ros rplidar_c1_launch.py \
  serial_port:=/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_ec8fc9bc95d5ef11afac704b49d2c684-if00-port0
```

## Device

The adapter is a **Silicon Labs CP2102N** (`10c4:ea60`), bound by `cp210x`, appearing as `/dev/ttyUSB0` with mode `crw-rw---- root:dialout`. `jarvis` is already in `dialout`, so **no udev rule was needed** — unlike the Teensy in [log 003](003-2026-08-04-teensy-rawhid-bringup.md), where flashing required one.

## First light

```
[rplidar_node]: RPLidar running on ROS2 package rplidar_ros. RPLIDAR SDK Version:2.1.0
[rplidar_node]: RPLidar S/N: CDA9E18DC2E699D7C89792F4370A416F
[rplidar_node]: Firmware Ver: 1.02
[rplidar_node]: Hardware Rev: 18
[rplidar_node]: RPLidar health status : 0
[rplidar_node]: RPLidar health status : OK.
[rplidar_node]: Start
[rplidar_node]: current scan mode: Standard, sample rate: 5 Khz, max_distance: 16.0 m, scan frequency:10.0 Hz
```

Health status `0` = OK. Worth remembering: the C1 reports `1` (Warning) or `2` (Error) here, and per its datasheet it **shuts down the laser on low input power** — so a brownout would surface as a non-zero status at this line, not as a dead device.

## Measurements

| Metric | Value | Reading |
|---|---|---|
| Scan rate | **10.008 Hz** · std dev **0.00099 s** | min 0.098 s, max 0.101 s over 33 samples — rock steady |
| `scan_time` | 0.09972 s | matches the 10 Hz nominal |
| CPU | **4.5 %** of one core (6 cores) | ≈0.75 % of the machine |
| RAM | 22.7 MB RES | negligible |
| Bandwidth | **58.64 KB/s** · 5.82 KB/msg | mean = min = max, so no short or dropped frames |
| `angle_increment` | 0.008715 rad = **0.499°** | **721 points per revolution** |
| `angle_min` / `angle_max` | −3.1241 / +3.1416 rad | full 360° |
| `range_min` / `range_max` | 0.15 m / **16.0 m** | |
| `time_increment` | 0.0001387 s | 7211 samples/s |
| `frame_id` | `laser` | launch default |

Sample of live data — real distances, with `inf` where nothing returns (correct, not an error):

```
[3.0807, 3.0807, 3.1260, 3.2135, 3.2135, 3.2660, 3.2660, 3.3198,
 3.3718, 3.3718, 3.4270, 3.4530, inf, 3.0290, 3.0290, 2.9887, ...]
```

### Against the datasheet

| Spec | Datasheet | Measured |
|---|---|---|
| Scan frequency | 8–12 Hz (10 typ) | 10.008 Hz |
| Sample rate | 5,000 /s | 7,211 /s from `time_increment` |
| Angular resolution | 0.72° | **0.499°** |
| Max range | 12 m @ 70% reflectivity | 16.0 m reported |

Better than spec on resolution and range. The datasheet's 12 m is the *white-target* figure; 16 m is what the driver advertises as the mode maximum. The angular figure differs because the driver angle-compensates (`angle_compensate:=true` by default), interpolating to a uniform grid.

## Decision validated

[Log 002](002-2026-08-04-usb-topology-and-peripheral-split.md) moved the lidar off Teensy `Serial1` onto Jetson USB. Every predicted benefit held:

| Predicted | Actual |
|---|---|
| Driver already exists, no firmware | ✅ Zero lines written. Launch file worked unmodified |
| CPU cost negligible (~3 %) | ✅ 4.5 % of one core of six |
| No 3.3 V level measurement needed | ✅ Open item **B5** stays deleted |
| MINI560 #1 freed | ✅ Lidar runs entirely off USB |
| 150 mV ripple constraint gone | ✅ No shared rail exists to pollute |
| Teensy `Serial1` freed | ✅ Available |

The Teensy-UART path would have required implementing the Slamtec protocol, a 4096-byte RX buffer, angle compensation, health polling, and `LaserScan` assembly — to arrive at worse timestamps. **Roughly two weeks of work avoided by spending ten minutes checking what was already installed.**

## Gotchas

### `/scan` missing from the first `ros2 topic list`

The node was publishing, but:

```
$ ros2 topic list
/parameter_events
/rosout
```

Stale **`ros2 daemon`** cache. Fixed by:

```bash
ros2 daemon stop     # restarts automatically on next use
```

After which `/scan` and `/rplidar_node` appeared normally. **This looks exactly like a node failing to publish.** Always bounce the daemon before believing a topic is absent.

### `pkill -f rplidar_node` kills its own shell

Over SSH, `pkill -f` matched the `bash -c` wrapper carrying the pattern in its own command line, killing the shell (exit 255) before it reached the target. The node survived.

Use `pgrep` to find the PID, then `kill` it:

```bash
pgrep -x rplidar_node        # then kill <pid>
```

## Stable device names

Both USB devices now have serial-number-keyed paths. **Use these in every launch file** — `/dev/ttyUSB0` and `/dev/ttyACM0` both move (see log 003, where the Teensy node shifted 0→1→0 with nothing unplugged):

```
lidar:  /dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_ec8fc9bc95d5ef11afac704b49d2c684-if00-port0
teensy: /dev/serial/by-id/usb-Teensyduino_USB_Serial_19627940-if00
```

The launch file defaults to `/dev/ttyUSB0`, so `serial_port:=` must be passed explicitly, or the default overridden in a project launch file.

## State at end

Lidar node **stopped** — the unit is not spinning. Nothing persists; relaunch with the command above.

## Follow-ups

| Action | Why |
|---|---|
| Project launch file with the by-id path baked in | Stops the port-numbering bug reaching production |
| Static TF from `laser` to `base_link` | SLAM needs the sensor's physical mount pose; `frame_id` is `laser` |
| Re-measure scan stability under motor load | Today's 0.001 s std dev is with motors idle. The real test is with current flowing |
| Confirm 16 m against a real target | Driver *advertises* 16 m; datasheet says 12 m at 70 % reflectivity |

## Takeaways

1. **Check what is already installed before writing anything.** `rplidar_ros` 2.1.4 with a launch file for this exact model was sitting in the workspace the whole time.
2. **A stale `ros2 daemon` mimics a broken node.** Bounce it before diagnosing.
3. **`pkill -f` over SSH can kill the shell running it.** `pgrep` then `kill` by PID.
4. **`dialout` covers `ttyUSB`/`ttyACM` but not `hidraw`** — which is why the lidar needed no udev rule and the Teensy did.

## Related

- [002](002-2026-08-04-usb-topology-and-peripheral-split.md) — the decision this validates
- [003](003-2026-08-04-teensy-rawhid-bringup.md) — Teensy bring-up; same by-id lesson, learned the hard way
- [`../ACTION-PLAN.md`](../ACTION-PLAN.md) item D8
