# 009 — LiDAR motor kept spinning after the service stopped

| | |
|---|---|
| **Date** | 2026-08-04 |
| **Type** | Bug — hardware left in a live state |
| **Status** | ✅ Fixed and confirmed by ear — panel off = silent, panel on = spinning |
| **Severity** | Medium — no damage, but a motor running unattended indefinitely |
| **Found by** | The user, by unplugging the lidar. That test is what cracked it |

---

## Symptom

`rplidar.service` stopped, no driver processes, unit `inactive` — and the lidar was still audibly spinning. Described as "a fan-like sound".

The only way to stop it was pulling the USB plug.

## Two wrong turns before the answer

**1. "It's probably the Jetson's fan."** Not unreasonable — the Orin Nano dev kit has active cooling, and the fan was measured running:

```
pwm1: 87/255 (~34%)   rpm: 1962   temps: ~54 °C
```

1962 RPM genuinely is "a fan". But the user unplugged the lidar and the noise stopped, settling it in one move. The fan was a real red herring, not a bad guess — it just wasn't the answer.

**2. "The C1 must free-run on USB power."** Also wrong, and the user's *second* observation is what disproved it:

> when i attached it, it was not making that sound again

Plugged back in, powered, **silent**. So the motor does not spin merely because it has power.

## Root cause

**The C1's motor holds its last commanded state, and process death is not a stop signal.**

Both halves matter:

- Per its datasheet the C1 has no MOTOCTL pin. The motor is closed-loop internal and cannot start or stop independently of the scan command. That is exactly *why* this happened — the motor obeys the last thing it was told and nothing else.
- `rplidar_node::stop()` does send the spin-down:

  ```cpp
  void stop() {
      drv->stop();
      drv->setMotorSpeed(0);   // ← this is the spin-down
      is_scanning = false;
  }
  ```

  But it only runs if `rclcpp` gets to execute its shutdown handler — which needs **SIGINT**. `run-lidar.sh` was sending **SIGTERM**, and `ros2 launch` does not reliably convert that into the graceful sequence. The node died with its orders still standing.

So: driver dies mid-scan → nothing ever says "stop" → motor spins until power is cut. Unplugging cleared it because power-cycling resets the command, and with no driver running nothing re-issued it.

**Nothing was "actively pushing it." Nothing had ever told it to stop.**

## Fix

Two layers, in `run-lidar.sh` and `rplidar.service`.

**1. SIGINT, so the driver can spin the motor down itself**

```ini
KillSignal=SIGINT
TimeoutStopSec=20
KillMode=mixed
```

```bash
kill -INT $LIDAR_PID
for _ in $(seq 1 20); do kill -0 $LIDAR_PID 2>/dev/null || break; sleep 0.25; done
kill -TERM $LIDAR_PID ${BRIDGE_PID:-} 2>/dev/null
```

**2. A raw STOP as a backstop, once the port is free**

```bash
# RPLIDAR protocol: 0xA5 0x25 = STOP.
f.write(b"\xA5\x25")
```

Sent unconditionally on every shutdown path — the trap *and* the "a child exited" path. Two bytes, idempotent. Redundant when the graceful path works, and the difference between silence and a motor running all night when it does not.

The `shutdown()` function is now called from both paths; previously the crash path only did `kill`, so a driver crash left the motor spinning too.

## Verification

Confirmed by the user, by ear, through the control panel:

> on panel when i turned it off it stopped and when i turned it on, it started

Machine-side after stop: unit `inactive`, no driver processes, `/dev/ttyUSB0` not held, device still enumerated on USB.

## Emergency stop, if it ever happens again

```bash
ssh user@<robot-ip> 'printf "\xA5\x25" > /dev/ttyUSB0'
```

Works whenever the port is free. No ROS, no driver.

## Corrections this forces elsewhere

`inventory.md` says the C1's motor "cannot start/stop independently of the laser scan command" — **true, and it reads as reassuring when it is actually the hazard.** It needs to say plainly that the motor keeps running until told to stop, and that killing the driver is not telling it to stop.

## Takeaways

1. **Process death is not a stop signal.** Anything holding physical state — a motor, a heater, a valve, a laser — needs an explicit shutdown command, and a path that survives the graceful one failing.
2. **ROS nodes need SIGINT, not SIGTERM.** `rclcpp` shutdown handlers do not run on SIGTERM through `ros2 launch`. Set `KillSignal=SIGINT` in any unit running a ROS node.
3. **Send the raw stop anyway.** Two bytes against an unattended motor is not a close call.
4. **"It holds its last command" is not the same as "it stops on its own."** The datasheet wording implied safety; it described the exact mechanism of the bug.
5. **Unplugging is a great diagnostic.** Two observations — silent after detach, silent after reattach — eliminated both the fan theory and the free-running theory in one move. Neither was reachable from the software side.
6. **A physical USB switch is still worth having**, now as a convenience rather than the fix.

## Related

- [008](008-2026-08-04-control-panel-camera-lidar.md) — introduced `rplidar.service` and `run-lidar.sh`, where this bug lived
- [004](004-2026-08-04-rplidar-c1-bringup.md) — lidar bring-up; motor behaviour recorded from the datasheet, not yet tested
- [007](007-2026-08-04-microros-bringup.md) — same family of lesson: killing a wrapper does not clean up what it started
