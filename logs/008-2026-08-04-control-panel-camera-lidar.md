# 008 — Control panel: authenticated camera stream + live LiDAR view

| | |
|---|---|
| **Date** | 2026-08-04 |
| **Type** | Feature |
| **Status** | ✅ Deployed and verified on `jarvis` |
| **Touches** | `robot-face/` — 4 new files, 3 modified |
| **Closes** | Nothing outright — **raises the bar on A6** (see Security) |

---

## What was added

Two panels on `/control`, alongside the existing mood and eye-colour controls:

| Panel | Does |
|---|---|
| **Camera** | Toggle on/off, live MJPEG stream of the Logitech Brio 500 |
| **LiDAR** | Toggle the lidar on/off, live polar plot of `/scan`, adjustable 1–16 m range |

## Security — the decision that shaped everything else

The panel had **no password** (open item A6). For mood control that is tolerable: worst case someone makes the robot look angry.

**A live camera feed of the user's home is a different category entirely.** So the camera and lidar endpoints are held to a higher bar than the rest of the panel: they require a password to **exist**, not merely a session.

This matters because of how `/login` behaves with no password set — it *auto-authenticates every visitor*:

```python
if not cfg.get("password_hash"):
    session["auth"] = True          # anyone on the LAN is now "logged in"
    return redirect(url_for("control"))
```

So `logged_in()` alone is worthless in that state. `sensor_guard()` checks both:

```python
def sensor_guard():
    if not logged_in():
        return jsonify(error="unauthorized"), 401
    if not password_is_set():
        return jsonify(error="password_required", message="..."), 403
    return None
```

### Verified against the exact attack

```
auto-authenticated visitor, no password set:
  mood POST      200   ← still works, cosmetic
  camera status  403   password_required
  camera stream  403   password_required
  camera start   403   password_required
  lidar start    403   password_required
```

And after a password is set:

```
wrong password  → 401
no session      → 401
```

`/api/lidar/ingest` is **localhost-only** — the app binds `0.0.0.0`, so that check is the only thing keeping it off the LAN. Confirmed **403 from the LAN IP**.

The UI reinforces it rather than silently failing: with no password the toggles render `disabled` under a 🔒 banner carrying the exact fix command.

> ⚠️ **A throwaway password was set during testing and is live.** Its value is deliberately not recorded here — a credential in git history outlives the credential. Replace it: `cd ~/robot-face && python3 manage.py set-password && systemctl --user restart robot-face`.

## Architecture — why the Flask app stays ROS-free

`rclpy` only imports with a ROS environment sourced. `robot-face.service` runs plain `/usr/bin/python3`, and **the face must be able to start when ROS is not running at all** — it is the robot's visible personality, not a ROS component.

So the lidar reaches the panel by one-way HTTP push:

```
rplidar.service (ROS env)                    robot-face.service (no ROS)
  ├─ ros2 launch rplidar_ros ──► /scan
  └─ scan_bridge.py  ──POST /api/lidar/ingest──►  lidar.py ──SSE──► browser canvas
```

A bridge crash cannot take the face down. The Flask app never imports ROS.

`scan_bridge.py` downsamples **721 → 360 points at 5 Hz**. Raw would be ~7 KB × 10/s per viewer for a canvas a few hundred pixels wide — far more resolution than can be drawn.

⚠️ **The bridge subscribes with `BEST_EFFORT` QoS.** The rplidar driver publishes best-effort; a default `RELIABLE` subscription would **silently never match** and the panel would show nothing with no error anywhere.

## Camera implementation

**One shared capture, many viewers.** V4L2 refuses two readers on one device, so a single grabber thread owns the handle and every HTTP viewer is served the latest frame from memory. N viewers cost the same as one.

Three details that matter:

- **Ask for MJPEG explicitly** (`CAP_PROP_FOURCC` = `MJPG`). Without it V4L2 negotiates raw YUYV — ~27 MB/s at 720p over USB, which caps the frame rate hard.
- **Stable device path.** `/dev/v4l/by-id/usb-046d_Brio_500_2437ZBD0PNK8-video-index0`. `/dev/video0` moves, and the Brio claims **two** nodes — `index1` is metadata, not capture.
- **Auto-release after 30 s unwatched.** A closed browser tab must not leave a webcam running in someone's home. The grabber loop tracks when a viewer last took a frame and shuts itself down.

Measured: **91 JPEG frames in 6 s ≈ 15 fps** at 1280×720, exactly the target.

720p15 is deliberate. The Brio does 1080p30, but every frame is JPEG-encoded on the CPU here and this is a monitoring view, not a recording.

## LiDAR unit — on demand, never at boot

`rplidar.service` is installed but has **no `[Install]` section**, so systemd reports it `static`:

```
$ systemctl --user list-unit-files rplidar.service --no-legend
rplidar.service static -
```

**It cannot be enabled.** The motor spins only when the panel starts it. Also `Restart=no` — if the panel stopped it, it must stay stopped, and a start that fails because the lidar is unplugged should surface as a failure rather than a restart loop.

Driver and bridge run under one unit, so systemd's default `KillMode=control-group` reaps both together — no orphan holding `/dev/ttyUSB0`. Verified after stop:

```
pgrep -af "rplidar_node|scan_bridge"  →  clean, no orphans
unit                                  →  inactive
```

## Visualisation

Client-side canvas from JSON, not server-rendered images: the Jetson has better things to do than rasterise plots, and zoom is then instant and free.

Frame convention is ROS REP-103 — x forward, y left, CCW angles — mapped so **forward is up** on screen and the robot's left appears on the left:

```js
var px = cx - d * Math.sin(a) * scale;   // canvas x right, ROS y left
var py = cy - d * Math.cos(a) * scale;   // canvas y down,  ROS x forward
```

`null` ranges (inf/NaN — no return) are skipped rather than drawn at `range_max`, which would paint a phantom wall. Nearer points render warmer, since those are the ones you can collide with.

## Verification

| Check | Result |
|---|---|
| Camera start | `running: true`, device present |
| Camera stream | **91 frames / 6 s ≈ 15 fps**, 9.06 MB |
| Camera stop | releases device, subsequent status 401 without session |
| LiDAR start via panel | `active: true` |
| LiDAR scanning | **43 scans in 15 s**, `last_scan_age 0.09 s` |
| SSE scan payload | 360 points, real ranges + `null` gaps, correct `angle_min`/`angle_increment` |
| LiDAR stop | unit `inactive`, **no orphan processes** |
| Panel renders | 5/5 new elements present |
| Guard, no password | camera + lidar **403**, mood **200** |
| Guard, wrong password | **401** |
| Ingest from LAN | **403** |

## Files

| File | |
|---|---|
| `robot-face/camera.py` | new — shared capture, grabber thread, idle auto-release |
| `robot-face/lidar.py` | new — `systemctl --user` control + SSE scan fan-out |
| `robot-face/scan_bridge.py` | new — ROS node, `/scan` → HTTP push |
| `robot-face/static/lidar-view.js` | new — canvas polar plot |
| `robot-face/deploy/rplidar.service` | new — on-demand unit, `static` |
| `robot-face/deploy/run-lidar.sh` | new — driver + bridge under one cgroup |
| `robot-face/app.py` | +8 routes, `sensor_guard()` |
| `robot-face/templates/control.html` | two panels, toggles, canvas |
| `robot-face/deploy/deploy.sh` | installs the lidar unit (not enabled) |

## Follow-ups

| Action | Why |
|---|---|
| **Replace the test password** | The throwaway set during testing is live on the LAN and gates a camera stream |
| HTTPS or a reverse proxy | The stream and the password cross the LAN in **plaintext HTTP**. Fine on a trusted home network, not beyond it |
| Camera resolution/fps control in the UI | Currently fixed at 720p15 in `camera.py` |
| Drive the face mood from robot state | Still hand-set only. Battery low, obstacle detected, arm moving are natural inputs — see [log 006](006-2026-08-04-robot-face-adoption.md) |
| Second camera (OV9281 pair) | Would need device selection; note the USB 2.0 bandwidth ceiling in [log 002](002-2026-08-04-usb-topology-and-peripheral-split.md) |

## Takeaways

1. **Auth state ≠ auth configured.** A panel that auto-authenticates when no password is set makes `logged_in()` meaningless. Gate sensitive features on the credential *existing*.
2. **Scale the gate to the consequence.** Mood and video do not deserve the same bar just because they share a page.
3. **Keep ROS out of the always-on app.** One-way HTTP push kept the face startable without ROS and isolated it from bridge crashes.
4. **`BEST_EFFORT` QoS or nothing appears** — and there is no error to tell you why.
5. **`static` units are the right shape for on-demand hardware.** No `[Install]` means it cannot accidentally be enabled at boot.
6. **Anything that turns on a camera needs an idle timeout.** A closed tab is not consent to keep filming.

## Related

- [006](006-2026-08-04-robot-face-adoption.md) — the panel this extends; A6 originated there
- [004](004-2026-08-04-rplidar-c1-bringup.md) — lidar bring-up, by-id path, `rplidar_ros`
- [002](002-2026-08-04-usb-topology-and-peripheral-split.md) — USB bandwidth limits on more cameras
- [007](007-2026-08-04-microros-bringup.md) — `set -u` / ROS sourcing, reused in `run-lidar.sh`
