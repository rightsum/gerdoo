# 057 — 2nd floor on: health check, new camera paths, arm sides relabelled (firmware 0.5.1)

| | |
|---|---|
| **Date** | 2026-11-06 |
| **Type** | Health check + fix |
| **Status** | ✅ Jetson, Teensy, 16 servos, drives, sonar, light healthy · ✅ Arm cameras on new paths, 224 tests, deployed · ✅ Firmware `microros-0.5.1`: left = IDs 11–18, right = 1–8 · ⚠️ Left arm has no joint limits · ⚠️ Neck (21/22) unplugged · ⚠️ Back-right sonar 3.6 cm |
| **Severity** | Medium |

---

## 1. Health check after the 2nd floor went on

The user: "installed seccond floor, check everything is healthy".

| Area | Result |
|---|---|
| Jetson | up 0 min, CPU 42 °C, GPU 40 °C, disk 5 % (42 of 916 GB); `robot-face`, `reactor-screen`, `micro-ros-agent` active, agent connected |
| Teensy | `HEALTH temp_c=43.1 loop_hz=999 restart=power_on` |
| Battery | `BATTERY main_v=12.064 … source=a0` |
| Drives | `IO en_L(7)=0 en_R(21)=0` (both off), `ENC L=1 R=1` |
| Sonar | `FL=16.5cm FR=14.1cm BL=39.1cm` **BR=3.6cm** |
| Light | auto, raw 1508 |
| Servo bus | 16 servos (1–8, 11–18), 11.9–12.1 V, 33–36 °C, torque off, no errors. **Neck 21/22 missing** (branch unplugged) |
| UPS | 11.95 V, −7.47 mV (on battery) |
| Not connected | USB hub, so no arm cameras, XVF3800 or lidar; face display (`card1-DP-1=disconnected`) |

**Glitch:** the very first console command after the Teensy boots still came back mangled (`ERR unknown_command HEARTBEAT seq=22 …`). The leading-newline fix (log 054) doesn't cover the first command after a boot. A retry works.

**Open:** back-right sonar at 3.6 cm is something right in front of it (a cable, the floor edge, the stand); see also log 049.

## 2. The USB hub and the arm cameras

- **First try:** the hub wasn't seen. Advice: Jetson USB-A only, reseat, check the hub's power LED, try another cable. On the second try it was seen.
- **The hub is now on Jetson port 2**, and the two OV9281 cameras on hub ports 1 and 4.
- **New by-path names:** `usb-0:2.2.1` and `usb-0:2.2.4` (were `2.1.2` / `2.1.3`, log 027). Both cameras report serial `SN0001`, so the USB path is the only way to tell them apart.
- **The camera mix-up:**

| Time | Change | Why |
|---|---|---|
| 11:38 | left = 2.2.1, right = 2.2.4 (a guess) | "do the recommended" |
| 11:50 | swapped | "right and left camera are vice versa" |
| 12:13 | **back to left = 2.2.1, right = 2.2.4** | "it was correct the cameras … i think i wired left and right arms vice versa" |

- **Files:** `robot-face/camera.py` (`ARM_LEFT_DEVICE`, `ARM_RIGHT_DEVICE`, with a dated comment) and `inventory.md`.
- **Verified:**
  - 224 tests pass on the Jetson;
  - deployed;
  - `/api/cameras/arm_left|arm_right/status` → `present:true`;
  - 51 frames in 2 s from each camera (cv2; `v4l2-ctl` isn't installed).

## 3. Arm sides relabelled in firmware (0.5.1)

The cameras were right; the arms were the other way round. The arm with servos 1–8 is mounted on the robot's **right**.

**The choice:** "Relabel in firmware" (recommended) or "swap the arms physically". **The user chose relabel.**

**Changes:**
- `teensy_microros.ino`: `Arm arms[2] = {{'L', 11, …}, {'R', 1, …}};`, plus a dated comment.
- `arm_types.h`: `uint8_t firstId; // L = 11..18, R = 1..8 (relabelled 2026-11-06)`.
- `FW_VERSION` → **`microros-0.5.1`**.
- Flashed with `make upload`: `INFO fw=microros-0.5.1 … built=Nov 6 2026 12:22:18`.
- `inventory.md`: "IDs: left 11–18, right 1–8".

**What follows the arm:**
- Joint limits are stored in the Teensy's EEPROM **per servo ID** (`RANGE_EEPROM_BASE = 256`, 8 bytes per ID).
- Calibration offsets live in the servos.
- So both stay with their physical arm.

| After the relabel | Reply |
|---|---|
| `ARM R STATE` (1–8) | limits `min=1180,1016,914,956,160,1066,166,1362 max=2916,3080,3182,3140,3936,3030,3930,2734`, multi-turn on |
| `ARM L STATE` (11–18) | `min=0,… max=4095,…`: **no limits, never calibrated** |

Before the relabel the 1–8 arm read **`torque=1`**: torque was on.

**Open:**
- **Don't move the left arm (11–18) until its limits are set and it's calibrated.**
- If the arms were physically swapped when the 2nd floor went on (rather than always mounted this way), re-check the right arm's limits at low strength.
- The neck's Y-splice (log 054) is in the **11–18 arm's cable**, now the left arm.

**Tooling:** the panel's arm cards poll the console and swallow replies. `console.py "ARM R STATE" 3 "ARM R"` (wait for that prefix, retry) gets through.

## Takeaways

- "Left" and "right" can mean the camera image, the arm, or the robot's side as seen from behind. Agree on which before changing anything.
- Store calibration with the thing it calibrates (per servo ID, or in the servo), never per "side". That made the relabel a two-line change.
