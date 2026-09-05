# 007 — micro-ROS on Teensy 4.1, Dual Serial, with the console kept alive

| | |
|---|---|
| **Date** | 2026-08-04 |
| **Type** | Bring-up — first ROS 2 node on the MCU |
| **Status** | ✅ Working — `/teensy_node` in the graph, pub + sub verified, reconnect verified |
| **Artifacts** | `teensy_microros/{teensy_microros.ino,Makefile,health_check.py}` |
| **Depends on** | [Log 003](003-2026-08-04-teensy-rawhid-bringup.md) (udev rules), [log 005](005-2026-08-04-headless-teensy-flashing.md) (headless flashing) |

---

## Result

```
$ ros2 node list
/teensy_node

$ ros2 topic list | grep teensy
/teensy/heartbeat
/teensy/led
/teensy/temperature
```

| Topic | Type | Direction | Rate |
|---|---|---|---|
| `/teensy/heartbeat` | `std_msgs/Int32` | Teensy → ROS | **1.000 Hz** |
| `/teensy/temperature` | `std_msgs/Float32` | Teensy → ROS | **1.001 Hz** |
| `/teensy/led` | `std_msgs/Bool` | ROS → Teensy | on demand |

Heartbeat jitter: std dev **0.00059 s**. Temperature reads 54.6 °C, matching the console.

## The central design choice — Dual Serial

**micro-ROS consumes the serial port it runs on.** That port becomes XRCE-DDS framing, so `Serial.print` debugging on it is impossible. On a robot still being brought up that is painful, and it is exactly what makes micro-ROS failures feel opaque.

Teensy solves it for free. `usb=serial2` (**Dual Serial**) gives two CDC interfaces:

```
16c0:048b  Dual Serial
  usb-Teensyduino_Dual_Serial_19627940-if00 -> ttyACM0   console   (Serial)
  usb-Teensyduino_Dual_Serial_19627940-if02 -> ttyACM1   micro-ROS (SerialUSB1)
```

**Proven working simultaneously.** While micro-ROS ran on `if02`, the console on `if00` answered `PING`, `INFO`, `HEALTH` and a new `ROS` command — including *while the agent was dead*. `health_check.py` from log 003 works unchanged against `if00`.

This is the single most valuable decision in the setup. Retrofitting it once the interface has grown would be miserable.

### How the transport was moved

`micro_ros_arduino`'s default transport is hardcoded to `Serial` in `src/default_transport.cpp` — but its four entry points are declared `__attribute__((weak))`. Defining strong versions in the sketch overrides them:

```cpp
extern "C" {
bool   arduino_transport_open (struct uxrCustomTransport *t) { SerialUSB1.begin(115200); return true; }
bool   arduino_transport_close(struct uxrCustomTransport *t) { SerialUSB1.end(); return true; }
size_t arduino_transport_write(struct uxrCustomTransport *t, const uint8_t *buf, size_t len, uint8_t *e);
size_t arduino_transport_read (struct uxrCustomTransport *t, uint8_t *buf, size_t len, int to, uint8_t *e);
}
```

**No library edits**, so a `micro_ros_arduino` upgrade cannot silently revert it.

⚠️ **Signature trap:** `micro_ros_arduino.h` declares `write`'s buffer as `const uint8_t *`, while `default_transport.cpp` defines it **non-const**. Matching the `.cpp` gives:

```
error: conflicting declaration of C function 'size_t arduino_transport_write(...)'
```

Match the **header** — it is what the sketch includes. C linkage means the symbol still overrides the weak definition either way.

## Toolchain

| Component | Version | Notes |
|---|---|---|
| `micro_ros_arduino` | **2.0.8-humble** | `precompiled=true`, 105 MB, in `~/Arduino/libraries/` |
| Precompiled lib | `src/imxrt1062/fpv5-d16-hard/libmicroros.a` | 8.0 MB, the Teensy 4.x target |
| `micro_ros_agent` | built from source in `~/ros2_ws` | 1 min 27 s |
| `vcstool` | 0.3.0 | `pip3 install --user` — no sudo |

### platform.txt patch — done surgically, not wholesale

Teensyduino cannot link precompiled archives without a patch. The library ships `extras/patching_boards/platform_teensy.txt` intended as a **wholesale replacement** — but it is based on an older platform.txt, and diffing showed it would have **reverted 1.62.0 improvements** (`recipe.advanced_size.pattern`, postbuild hook changes).

Applied only the two changes that matter, to the installed file, with `platform.txt.orig` kept as backup:

```
compiler.libraries.ldflags=                       # new, line 34
recipe.c.combine.pattern=... {object_files} {compiler.libraries.ldflags} "..."
```

⚠️ **This patch lives in `~/.arduino15` and will be lost if the Teensy core is reinstalled or updated.** Symptom would be a wall of `undefined reference` at link time.

## Memory cost

| | bring-up | micro-ROS | |
|---|---|---|---|
| FLASH code | 13,100 B | **264,428 B** | 7.78 MB still free |
| RAM1 variables | 4,992 B | **47,744 B** | 312 KB free for locals |
| RAM1 code | 10,552 B | 132,536 B | |
| RAM2 | 12,416 B | 24,768 B | 499 KB free for malloc |
| Loop rate | 7.06 MHz | **4.36 MHz** | agent-ping polling |

micro-ROS is heavy — **20× the flash** — but the Teensy 4.1 absorbs it without strain. The loop-rate drop is the connection state machine polling, not the executor.

## Reconnection state machine

A naive micro-ROS sketch **hangs forever if the agent is not up at boot, and stays dead if the agent restarts.** On a robot both happen routinely. So the firmware runs `WAITING_AGENT → AGENT_AVAILABLE → AGENT_CONNECTED → AGENT_DISCONNECTED`, pinging for an agent, building entities when one appears, destroying them cleanly when it goes.

Verified end to end:

```
--- no agent ---              ROS agent=waiting   connects=1 drops=1
--- agent started ---
t+08s                         ROS agent=connected connects=2 drops=1
t+16s ... t+32s               ROS agent=connected connects=2 drops=1
```

**Recovered within 8 s, unattended.** Console stayed responsive throughout, including while disconnected — the payoff of Dual Serial.

`destroyEntities()` sets the session-destroy timeout to 0 first (`rmw_uros_set_context_entity_destroy_session_timeout`), otherwise teardown blocks trying to talk to an agent that is already gone.

## Agent as a systemd user service

The agent has to survive reboots and its own crashes, so it runs as a **user** unit — `systemctl --user`, no root — modelled on `robot-face.service` ([log 006](006-2026-08-04-robot-face-adoption.md)).

```
~/.config/systemd/user/micro-ros-agent.service
~/gerdoo/teensy_microros/deploy/run-agent.sh
```

Three decisions in it, each fixing something that bit during this session:

**1. Exec the agent binary directly, never `ros2 run`.** That wrapper is what orphaned a process holding `/dev/ttyACM1` (below). Exec'ing the binary makes systemd's `MainPID` the agent itself:

```
$ systemctl --user show micro-ros-agent -p MainPID --value | xargs ps -o args= -p
/home/jarvis/ros2_ws/install/micro_ros_agent/lib/micro_ros_agent/micro_ros_agent serial --dev /...
```

**2. Wait up to 60 s for the device.** The Teensy vanishes for ~6 s on every reflash and may enumerate after the user session starts. Without the wait, systemd burns its restart budget on a board that simply is not up yet.

**3. Key the device path to the serial number, not a glob.** Once the arm Teensy exists, a glob would race between two boards.

### Verified: full crash recovery, unattended

```
kill -9 <agent pid>
   ↓
systemctl --user is-active   → active        (NRestarts=1, new pid)
   ↓
console: ROS agent=connected connects=4 drops=3
   ↓
ros2 topic hz /teensy/heartbeat → 1.000 Hz
```

**Two independent recovery layers**, which is what makes this robust:

| Layer | Handles |
|---|---|
| systemd `Restart=always` | agent crash, reboot, device unplug |
| Teensy state machine | agent gone/returned, with no reflash |

⚠️ **Reboot survival is inferred, not proven.** The unit is `enabled` and symlinked into `default.target.wants`, but it depends on gdm autologin starting the `jarvis` session — same assumption as `robot-face`. Confirm on the next Jetson reboot.

### ⚠️ `set -u` breaks ROS setup scripts

The unit failed instantly — `status=1/FAILURE` after 9 ms — with the device plainly present:

```
/opt/ros/humble/setup.bash: line 8: AMENT_TRACE_SETUP_FILES: unbound variable
```

**ROS setup scripts are not `set -u` clean.** `setup.bash` reads that variable unconditionally, so any `set -u` script that sources it dies on line 8. Fixed by scoping `set +u` around the sourcing rather than abandoning the check:

```bash
set +u
source /opt/ros/humble/setup.bash
source "$HOME/ros2_ws/install/local_setup.bash"
set -u
```

Worth knowing generally: **every wrapper script that sources ROS needs this.**

## Gotchas

### Killing `ros2 run` does not kill the agent

The first reconnection test appeared to fail — the Teensy detected the drop (`drops=1`) but would not reconnect for over 50 s.

Cause: `kill <pid-of-ros2-run>` killed the **Python wrapper**, leaving the real binary alive:

```
198968 .../lib/micro_ros_agent/micro_ros_agent serial --dev ...   ← orphan, still holding ttyACM1
199489 /usr/bin/python3 /opt/ros/humble/bin/ros2 run micro_ros_agent ...
199515 .../lib/micro_ros_agent/micro_ros_agent serial --dev ...   ← the new one
```

**Two agents fighting over the same serial device.** The state machine was fine; the test was broken. Kill the binary, not the wrapper:

```bash
pgrep -f "lib/micro_ros_agent"      # the real process
```

### Stale `ros2 daemon` again

`ros2 node list` and `ros2 topic list` showed nothing while `ros2 topic hz /teensy/heartbeat` reported a clean 1.000 Hz. Same trap as [log 004](004-2026-08-04-rplidar-c1-bringup.md). `ros2 daemon stop` fixes it. **Trust `hz`/`echo` over `list`.**

### `rosdep` wants sudo

`build_agent.sh` fails on `sudo -H apt-get install -y libncurses-dev`. Building directly with `colcon build --packages-up-to micro_ros_agent` succeeded — the dependency was **not actually needed** for this build.

### by-id name changes with USB type

`usb=serial` → `usb-Teensyduino_USB_Serial_...`; `usb=serial2` → `usb-Teensyduino_**Dual**_Serial_...`. The Makefile glob was pinned to the former and stopped matching. Widened to `usb-Teensyduino_*Serial_*-if00`.

## Running it

The agent runs itself — it is a systemd user service, started at login and restarted on failure. Nothing to launch by hand.

```bash
# agent control
systemctl --user status  micro-ros-agent
systemctl --user restart micro-ros-agent
journalctl --user -u micro-ros-agent -f

# console — works any time, agent up or down
cd ~/gerdoo/teensy_microros && make health

# actuate
ros2 topic pub --once /teensy/led std_msgs/msg/Bool "{data: true}"
```

To run it manually instead (debugging), stop the unit first so two agents do not fight over the port:

```bash
systemctl --user stop micro-ros-agent
~/gerdoo/teensy_microros/deploy/run-agent.sh
```

## Follow-ups

| Action | Why |
|---|---|
| ~~systemd user unit for the agent~~ | ✅ **Done this session** — see above. Crash recovery verified |
| **Confirm the unit survives a real reboot** | Currently inferred from `enabled` + the `robot-face` precedent, not observed |
| Re-apply platform.txt patch after any core update | Silent breakage otherwise; `platform.txt.orig` is the reference |
| Custom messages for real telemetry | `Int32`/`Float32` do not carry encoder ticks, battery volts, or motor state |
| Decide `ros2_control` boundary | micro-ROS suits lights/weather/servo goals. The drive loop likely wants a `hardware_interface` over its own protocol — see [log 002](002-2026-08-04-usb-topology-and-peripheral-split.md) |
| Re-measure loop rate under real load | 4.36 MHz is with no peripherals attached |

## Takeaways

1. **Dual Serial first, always.** micro-ROS eats its port; losing the console on a robot under bring-up is not worth it, and retrofitting later is painful.
2. **Override the weak transport symbols, do not edit the library.** Survives upgrades.
3. **Match the header signature, not the `.cpp`.** They disagree on `const`.
4. **Patch platform.txt surgically.** The bundled replacement is stale and silently reverts core improvements.
5. **The connection state machine is not optional** on a robot. Without it, an agent restart means a firmware reflash.
6. **`ros2 run` is a wrapper.** Killing it orphans the real process — which then holds the serial device. Exec the binary directly in service units.
7. **ROS setup scripts are not `set -u` clean.** Scope `set +u` around every `source` of them.
8. **Recover in two layers.** systemd restarts the agent; the firmware reconnects to it. Either alone leaves a hole.

## Related

- [003](003-2026-08-04-teensy-rawhid-bringup.md) · [005](005-2026-08-04-headless-teensy-flashing.md) — what made flashing possible
- [002](002-2026-08-04-usb-topology-and-peripheral-split.md) — Dual Serial recommended here first
- [004](004-2026-08-04-rplidar-c1-bringup.md) — same stale-daemon trap
