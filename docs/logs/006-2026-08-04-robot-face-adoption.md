# 006 — Adopting the `robot-face` kiosk into this repo

| | |
|---|---|
| **Date** | 2026-08-04 |
| **Type** | Adoption — pre-existing subsystem brought under this project |
| **Status** | ✅ Adopted at `robot-face/`, verified against the running deployment |
| **Origin** | Separate session, ~2026-07-05. Memory: `-Users-rightsum/memory/robot-face-project.md` |
| **Live** | Running on `jarvis` right now — service `active`+`enabled`, Firefox kiosk up |

---

## What this is

An animated robot face that takes over the robot's 5.5" panel in Firefox kiosk mode, plus a web control panel on the LAN to change **mood** and **eye colour** live.

```
Desktop browser ──(login, pick mood)──▶  Flask app  ──(SSE push)──▶  Firefox kiosk (the face)
     /control                          on the robot                      /
```

| | |
|---|---|
| Face (on the robot) | `http://localhost:8080/` |
| Control panel (from a desktop) | `http://<robot-ip>:8080/control` |
| Backend | Flask 3.1.3 (system Python, no Node) |
| Service | **user** systemd unit `robot-face` — `systemctl --user`, no root |
| Kiosk | `~/.config/autostart/robot-face-kiosk.desktop`, ~8 s into session |
| Live push | Server-Sent Events — mood changes appear with no refresh |
| Moods | `auto` (autonomous cycle) · idle · happy · curious · love · thinking · surprised · sleepy · sad · angry |
| Colours | amber `#FFAE1E` · orange `#FF7A1E` · yellow `#FFD34D` · cyan `#2AD4FF` |

The `<robot-face>` canvas web component came from a Claude Design project (`44696c03-7c4d-438b-8852-e3481184c04f`).

## Why it was adopted now

It surfaced sideways. While flashing the Teensy I started the Teensy Loader GUI on `DISPLAY=:0` and reported its window — but the panel shows the face, full-screen, permanently. The loader window was never visible. See [log 005](005-2026-08-04-headless-teensy-flashing.md).

That made the point: **the display is not a spare terminal, it is a dedicated output owned by a running service.** Anything assuming a usable desktop on this robot is wrong. Worth having in-repo rather than in a separate directory nobody cross-references.

## Verification before adopting

The Mac source at `/Users/rightsum/robot-face` and the live deployment at `/home/jarvis/robot-face` were compared file by file:

```
SAME  app.py                          SAME  static/robot-face-gl.js
SAME  manage.py                       SAME  static/robot-face.js
SAME  README.md                       SAME  templates/control.html
SAME  requirements.txt                SAME  templates/face.html
SAME  demo.html                       SAME  templates/login.html
SAME  .gitignore                      SAME  deploy/deploy.sh
SAME  deploy/firefox-kiosk.user.js    SAME  deploy/robot-face.service
SAME  deploy/robot-face-kiosk.desktop
```

**15/15 identical (sha256).** No drift, so the adopted copy is known-good and matches what is actually running. Had they differed, the running copy would have been authoritative and the difference would have needed resolving first.

## What was copied — and what was not

Copied into `robot-face/` (96 KB, 15 files). **Deliberately excluded:**

| Excluded | Why |
|---|---|
| `config.json` | Device-specific. Contains the Flask **`secret_key`** and (once set) the control-panel password hash |
| `state.json` | Live mood/colour, rewritten constantly at runtime |
| `__pycache__/` | Build artefact |

The project's own `.gitignore` already excluded all three — good hygiene from the original session, carried over unchanged.

## ⚠️ Open security item — control panel has no password

`config.json` on the robot has **no `password_hash` key**. Per `app.py:174`:

```python
if not cfg.get("password_hash"):
    # No password configured yet: control panel is open. Warn in the UI.
```

**Anyone on the LAN can open `http://<robot-ip>:8080/control` and change the robot's face.** The UI shows a warning banner, but there is no access control.

Severity is low — worst case is someone making the robot look angry — but it is a service listening on all interfaces with authentication disabled, and it was already flagged as wanted in the origin session's notes.

Fix, on the robot:

```bash
cd ~/robot-face
python3 manage.py set-password      # prompts, hidden input
systemctl --user restart robot-face
```

Tracked as ACTION-PLAN **A6**.

## Device gotchas carried over from the origin session

These were discovered the hard way and are easy to regress:

**Firefox software-renders on Jetson.** It blocklists WebRender and accelerated canvas on aarch64/Tegra, giving a laggy face. Fixed by forcing GPU in a dedicated kiosk profile `~/.robotface-ff`:

- prefs `gfx.webrender.all`, `gfx.canvas.accelerated`, `gfx.x11-egl.force-enabled`
- launch env `MOZ_X11_EGL=1 MOZ_WEBRENDER=1`

Confirmed still working today — the process list shows a real GPU content process:

```
firefox -contentproc ... -appDir /usr/lib/firefox/browser 1 gpu
```

**`xfce4-screensaver` blanks the panel** and ignores `xset`. Disabled via `xfconf /saver/enabled=false` plus a `Hidden=true` autostart override.

**Display is physically 1080×1920**, rotated to 1920×1080 landscape by a pre-existing `rotate-display` autostart, which also calibrates the touchscreen.

**Two renderers** (config `renderer`): `robot-face-gl.js` is WebGL/SDF — guaranteed GPU, glow computed in-shader, auto-falls back to 2D. `robot-face.js` is GPU-accelerated Canvas 2D.

## Power — partially answers open item B7

Measured in the origin session at 30 fps:

| Renderer | GR3D | Board power |
|---|---|---|
| Canvas 2D | ~18 % | 5.79 W |
| WebGL | ~30 % | 5.85 W |

Conclusion recorded then: **total board power (~5.9 W) is display-dominated, not renderer-dominated.** Renderer, resolution and fps choices move it only slightly. The one real win was dropping 60→30 fps, worth ~0.5 W.

**This does not close B7.** That figure is *Jetson board* power. Whether it includes the panel depends on how the panel is fed — and per [log 002](002-2026-08-04-usb-topology-and-peripheral-split.md) the plan is HDMI for video with USB only for driver-board power, which would put the panel **outside** this measurement. B7 still needs a meter on the panel's own supply.

What it does settle: **do not tune the renderer for battery life.** The screen being on is the cost; which renderer draws it is noise. Turning the panel off during autonomous runs is the only meaningful saving.

## Deployment

```bash
./deploy/deploy.sh          # rsync + install user service + autostart, no sudo
```

Defaults to `ROBOT=user@<robot-ip>` — overridable:

```bash
ROBOT=user@192.168.55.1 ./deploy/deploy.sh    # USB fallback, see log 001
```

Worth knowing given log 001: when wifi drops, the wifi IP in that default is useless and the USB link still works.

## Integration questions this raises

Not decided, recorded so they are not forgotten:

1. **Should mood be driven by ROS 2?** The robot's actual state — battery low, obstacle detected, arm moving — is the natural input to an expression. Currently mood is only ever set by hand through the panel. A small ROS node subscribing to robot state and POSTing to the Flask app would close that loop, and fits the "AI manages the tools" goal.
2. **Panel on/off control.** No way to blank the screen from software today. Relevant to battery life and to B7.
3. **Port 8080 on all interfaces** — see the security item above.

## Takeaways

1. **The robot's display is owned by a service**, not free for ad-hoc windows. Anything expecting a usable desktop on `jarvis` is wrong.
2. **Verify source against deployment before adopting.** 15/15 matched here; had they not, the running copy is the truth.
3. **Never adopt runtime config.** `config.json` carries a `secret_key`; it stays on the device.
4. **A service listening on all interfaces with auth disabled is a finding**, even when the impact is cosmetic.

## Related

- [001](001-2026-08-04-jetson-wifi-unreachable.md) — the USB fallback that `deploy.sh` can target
- [002](002-2026-08-04-usb-topology-and-peripheral-split.md) — how the panel is wired; B7
- [005](005-2026-08-04-headless-teensy-flashing.md) — the kiosk hid the loader window
- `robot-face/README.md` — full operational detail
