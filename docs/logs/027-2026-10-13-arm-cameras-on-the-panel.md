# 027 — Arm cameras on the panel: one serial for two cameras, and a 210 fps floor

| | |
|---|---|
| **Date** | 2026-10-13 |
| **Type** | Bring-up + design decision — the two OV9281 gripper cameras |
| **Status** | ✅ Both cameras working, on the control panel, each with its own toggle · ✅ Left camera reflashed with the right camera's firmware (2026-10-14), now 30 fps and normally exposed |
| **Severity** | Low — new feature; three traps found before they cost anything |

---

## Context

Two ElRobot follower arms ([norma-core/hardware/elrobot](https://github.com/norma-core/norma-core/tree/main/hardware/elrobot))
are on the robot, each with an OV9281 global-shutter camera (module S1M03) on
the gripper. The panel should show either one on demand. [Log 002](002-2026-08-04-usb-topology-and-peripheral-split.md)
planned for these cameras: set `uvcvideo quirks=128` first, and step down to
640×400 if the second camera refuses.

## Evidence

**Both enumerate, as Sonix `0c45:636d`, on the VIA hub behind the Realtek hub:**

```
Bus 001 Device 042: ID 0c45:636d Microdia USB 2.0 Camera     # port 2.1.3 → /dev/video2
Bus 001 Device 045: ID 0c45:636d Microdia USB 2.0 Camera     # port 2.1.2 → /dev/video4
```

**Trap 1 — both report serial `SN0001`.** `/dev/v4l/by-id/` keeps one link
for the pair, whichever enumerated last:

```
usb-Sonix_Technology_Co.__Ltd._USB_2.0_Camera_SN0001-video-index0 -> ../../video4
```

`/sys/bus/usb/devices/1-2.1.{2,3}/serial` both read `SN0001`. The by-id rule
in this repo cannot tell them apart. The port path is the only stable name:

```
/dev/v4l/by-path/platform-3610000.usb-usb-0:2.1.2:1.0-video-index0
/dev/v4l/by-path/platform-3610000.usb-usb-0:2.1.3:1.0-video-index0
```

**Trap 2 — the two cameras are not the same firmware.** There is no
`v4l2-ctl` on the robot, so the formats were enumerated with raw
`VIDIOC_ENUM_FRAMEINTERVALS` ioctls:

```
/dev/video2  MJPG 1280x720 fps=[120, 90, 60, 30]   640x400 fps=[210, 120, 90, 60, 30]   + YUYV
/dev/video4  MJPG 1280x720 fps=[120]               640x400 fps=[210]                     MJPEG only
```

`video4` cannot be asked for less than its maximum rate. `ffmpeg -framerate 30`
on it ran at 120 fps.

**Bandwidth.** `quirks` still reads `4294967295`. The `modprobe.d` file from
log 002 was never written, because it needs sudo. Brio and both arms streaming
at once:

| Arms at | Open order | Result |
|---|---|---|
| 1280×720 | arms first | Brio: `No space left on device` |
| 1280×720 | Brio first | `video2`: `No space left on device` |
| 640×400 | arms first, Brio 2 s later (×2) | all three stream — Brio 25, arm 30, arm 211 fps |
| 640×400 | all at once | all three stream |

`No space left on device` is how this kernel reports the isochronous
reservation failing. It is the same failure as log 002's
`Not enough bandwidth`, reported from `VIDIOC_STREAMON`.

## Decision

- **Arms run at 640×400, MJPEG.** This is the 16:10 step-down from log 002, and
  it works in any open order without the quirk.
- **Published at 30 fps, by frame count.** Every Nth frame goes out, where N
  is the driver's negotiated rate divided by 30, rounded up: 7 for
  `video4` at 210 fps, 1 for `video2` at 30 fps.
- **Addressed by port path**, overridable with `ROBOT_ARM_CAMERA_LEFT` and
  `ROBOT_ARM_CAMERA_RIGHT`. **Each camera must stay in its own hub port.**
  Swapping the cables swaps left and right on the panel.

## Wrong turns

- **The first cap used the clock**: publish if 1/30 s had passed since the last
  frame. A camera delivering *exactly* 30 fps has frames arrive a hair early
  from USB jitter, and they get dropped. That halves the rate. Caught on
  review, before deploy. Frame counting has no clock to be early against.
- **The frame-count cap delivered 17 fps, not 30, on `video4`.** 17 × 7 ≈ 120,
  so the grabber was seeing ~120 of the 210 frames. The cause was
  `CAP_PROP_BUFFERSIZE=1`, which the head camera uses for freshness. With one
  buffer, the driver has nowhere to put a frame while that buffer is being
  handed back:

  ```
  buffers 1  negotiated 210.0  grab rate 124
  buffers 2  negotiated 210.0  grab rate 211
  buffers 4  negotiated 210.0  grab rate 211
  ```

  A capped camera now gets 2 buffers, which adds 5 ms of latency at 210 fps.
  Uncapped cameras (the Brio) keep 1.

## Fix

- `robot-face/camera.py`: `Camera(max_fps=, label=)`, frame-count cap with
  `grab()`/`retrieve()` split (dropped frames are dequeued, never copied), a
  second buffer when capped, and a `cameras` registry
  (`head`, `arm_left`, `arm_right`). `camera` is still the head camera.
- `robot-face/app.py`: `/api/cameras/<name>/status|start|stop` and
  `/cameras/<name>/stream.mjpg`, behind the same `sensor_guard()` as the head
  camera. The old `/api/camera/...` routes are unchanged. The face tracker
  uses them.
- `robot-face/templates/control.html`: an **Arm cameras** card with one row
  per gripper. Each row has its own toggle, status LED and stream.
- Tests: `tests/test_camera.py` (cap, grab-not-retrieve, no loss at the cap,
  buffer count) and `tests/test_camera_routes.py` (routes, auth, 404/400/503,
  panel render).

## Verification

134 tests pass on the Jetson. Deployed, then streamed all three cameras through
the panel's own endpoints for 6 s:

```
arm_left:  30 fps, 364 KB/s
arm_right: 30 fps, 913 KB/s
head:      25 fps, 3998 KB/s
robot-face CPU: 6–13 %
```

The arms add ~10 Mbps together. Most of the wifi budget is the Brio at 720p,
as before.

**Not covered:**
- **Left and right were a guess at first.** Port 2.1.2 is called left, and
  the reflash below confirmed it: the dark camera taken off the left arm is
  the one that came back on 2.1.2. If the cameras are ever re-cabled and the
  sides swap, change the two `by-path` defaults in `camera.py`.
- **`quirks=128` would not help.** See the follow-up below.
- **The panel card was not seen in a browser.** It renders under test, but
  rendering it on the robot needs the panel password.

## Follow-up — "extremely dark, and low quality"

> the export looks extremely dark and at the same time low quality

Seen on the panel at night. The left feed was nearly black and the right one
was grey and soft. The two complaints have different causes.

**First diagnosis — the exposure ceiling. Partly true, and the wrong cause.**
Both cameras run identical controls: auto exposure, gain 15, gamma 100.
Measured through the panel's own stream:

```
arm_left:  mean=10/255   (210 fps camera)
arm_right: mean=100/255  (30 fps camera)
```

A frame cannot be exposed for longer than it lasts: 4.8 ms at 210 fps,
against 33 ms at 30. Manual exposure on the left camera proved the ceiling is
real. At 4 ms the mean was 20. At 10 ms and 30 ms the frames came back black,
because both are longer than the 4.76 ms frame.

On that basis gamma 180 was shipped for the left camera. **It was the wrong
fix, and it has been reverted.** The two cameras had not been pointed at the
same scene, so that comparison measured the scenes as much as the cameras.

**The decisive test — run the right camera at the left camera's rate.** The
user pushed back: same brand, same configuration, same direction, yet only
one looked bad. The descriptors confirmed different firmware. Both report
`bcdDevice 0100`, but the left camera has no 30/60/90 fps intervals and no
YUYV format. So the right camera was forced to 210 fps (sharpness is the
variance of the Laplacian):

```
LEFT  @210  mean 44   sharpness 3
RIGHT @210  mean 86   sharpness 23
RIGHT @30   mean 138  sharpness 23
```

The right camera at 210 fps is crisp and adequately bright. **The frame rate
is not why the left camera looks bad.** Then the left camera alone, at both
of its resolutions, seconds apart:

```
LEFT 640x400@210  mean 44   sharpness 3.1
LEFT 1280x720@120 mean 132  sharpness 3.2
```

It is equally blurry in both modes, with a large glow around the lamp in both.
The **blur** was the left lens: a smudge, gone after cleaning. The darkness
remained after cleaning, and the firmware was its cause after all (below).
The darkness was not secondary. It is what the reflash fixed.

**Soft, both cameras — resolution and sensor.** 640×400 is stretched across
the card, and the OV9281 is a **monochrome** sensor. No setting will make it
colour.

**720p is not available while the Brio runs.** The 640×400 decision was based
on the assumption that `quirks=128` could later buy 720p. Reading the kernel
(`uvc_video.c` 5.15.148, line 200):

```c
if (!(format->flags & UVC_FMT_FLAG_COMPRESSED) &&
    stream->dev->quirks & UVC_QUIRK_FIX_BANDWIDTH && ...
```

The quirk only rewrites the bandwidth for **uncompressed** formats. These
cameras are MJPEG-only, so log 002's central recommendation never applied to
them. Combinations, each camera opened 1.5 s after the last:

| Brio 720p + | Result |
|---|---|
| left 640×400 + right 640×400 | ✅ all three, in all four open orders tried |
| left 720p@120 + right 640×400 | ❌ right: `No space left on device` |
| left 640×400 + right 720p@30 | ❌ right: `No space left on device` |
| both 720p | ❌ right: `No space left on device` |
| *(no Brio)* both arms 720p | ✅ |

The per-mode endpoint sizes in sysfs are small: 800–1024 B per microframe for
the arms, 896 for the Brio. They do not add up to the failure, so the host's
accounting is not simply additive. That was not chased further; the table is
the rule.

## Fix — reflashing the left camera with the right camera's firmware

**Two builds of one product.** Each camera's flash carries a build tag:

```
left:  ZXCZ-QTX--2805----OV9281-50-221118L000   (2022-11-18)
right: -QTX-000I-2805----OV9281-50-240523XP00   (2024-05-23)
```

They share the same board (`2805`), sensor (`OV9281-50`), Sonix **SN9C286**
bridge (chip id `0xAA` at ASIC `0x101F`) and SDK library versions. Only the
2024 build lists the slower frame rates.

**Reading over USB works from Linux.** The vendor extension unit is unit 3:
selector 1 reads ASIC registers, and selector 3 reads flash 8 bytes at a
time. Both are documented in Kurokesu/C1_SONIX_Test_AP. `~/cam-firmware/sonix_read.py`
on the robot dumps the flash this way, and two reads of each camera were
identical. **It only reaches the first 128 KB.** The chip is 256 KB, and the
2022 build keeps code above 128 KB.

**Writing over USB from Linux does not work.** Writes need an unlock and an
erase that are not publicly documented for this chip. A register map published
for the SN9C292B does not apply to the SN9C286. A read-only probe using it
timed out, and its cleanup changed four RAM/register bytes. They were restored
from the values read before the probe, and the camera kept streaming. The
flash was never touched.

**What worked: Arducam's CommonBurnerAP v1.0.1.4** (from
docs.arducam.com/UVC-Camera/Firmware-Burning), in a Windows 11 ARM VM on the
Mac (UTM, the camera passed through over USB). A different, unofficial burner
(`sonix_burn.exe`) stalled at "erase and check" and changed nothing. That was
verified afterwards: CommonBurnerAP's export matched the 2022 original
exactly. CommonBurnerAP's tabs:

- 烧录 = burn
- 辅助功能 = auxiliary: 获取F/W版本 (read version), 导出ROM (export ROM),
  擦除Flash (erase)

It rejects any image that is not the full 256 KB ("固件的大小不匹配", size
mismatch).

Sequence:

1. Export the left camera's ROM: 256 KB, SHA-256 `ea6a0187…8232`. Its first
   128 KB matched the Linux dump byte for byte.
2. Export the right camera's ROM: SHA-256 `d31dff63…83fa7`. Its first half
   equals the right Linux dump. Its upper half is blank.
3. Burn the right image onto the left camera. Check with 获取F/W版本 before
   burning, so the wrong camera is never written.

Both full images are kept, on the robot in `~/cam-firmware/` and on the Mac in
`~/VMs/burner/`: `left_original_FULL_256k.src` and `right_2024_FULL_256k.src`.

**Verification, on the robot after the burn:**

```
port 2.1.2  MJPG 640x400 fps=[210, 120, 90, 60, 30]   + YUYV   (was: [210] only)
left_after_burn.bin  cb3cb894…5f31   == right_dump1.bin  cb3cb894…5f31
panel: arm_left 30.7 fps, arm_right 30.7 fps, both passthrough
```

The left frame is sharp and normally exposed in daylight. The frame-rate cap
in `camera.py` now divides by 1 for both cameras, and stays as a guard for any
module that arrives with max-only firmware.

**Last difference: the right lens.** With both cameras on the same firmware,
mode and settings, pointed at the same shelf, the right one looked softer.
Sharpness was 11.2 against the left's 17.4, and the softness showed on the same
objects. That is the same smudge symptom the left lens had. After the right
lens was cleaned, the final reading was:

```
arm_left:  31 fps  sharpness 38.8
arm_right: 31 fps  sharpness 37.6
```

A sharpness readout made the cleaning measurable instead of judged by eye. It
is the variance of the Laplacian over the panel stream, refreshed every 0.5 s.

## Takeaways

1. **A serial number is only stable if the vendor bothered to make it unique.**
   Two cheap UVC modules shipped with `SN0001`. Check
   `/sys/bus/usb/devices/*/serial` before trusting `by-id`.
2. **"Ask for 30 fps" is a request, not a setting.** Enumerate the frame
   intervals. A camera that offers only its maximum rate has to be capped in
   software.
3. **Rate-limit by count, not by clock, when the source rate is known.** A
   clock limit at the source's own rate drops frames to jitter.
4. **One V4L2 buffer is a frame-rate limit.** It is fine at 25 fps and
   costs 40 % of frames at 210.
5. **Read the driver before trusting a quirk.** `quirks=128` was planned,
   written into the inventory, and almost applied, on the strength of a
   description. One `if` in the source showed that it cannot touch MJPEG.
6. **Compare like with like, and expect two causes.** Forcing the good camera
   into the bad one's mode took one command. It showed the blur was the lens,
   which I then wrongly read as "the firmware is not the problem." After the
   lens was cleaned the darkness remained, and the firmware was its cause.
   Two cameras pointed at different scenes are not a comparison.
7. **Check a module's frame-rate list before mounting it.**
   `/tmp/enum_fps.py`-style enumeration takes one second. The same listing
   from the same seller shipped two firmware builds.
8. **A vendor dump is the size the vendor reads.** The Linux reader stopped
   at 128 KB of a 256 KB chip, so the image in hand was half a firmware. The
   burner's size check caught it before anything was written.
