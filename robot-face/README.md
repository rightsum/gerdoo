# Robot Face

An animated robot face that takes over the robot's 5.5" screen in Firefox kiosk
mode, plus a password-protected web panel (reachable from any device on your home
LAN) to change its **mood** and **eye colour** live.

The face is the *Robot Face* design (imported from Claude Design) — a canvas
`<robot-face>` web component with 9 expressions + an autonomous "auto" mode.
Mood changes push to the face instantly over Server-Sent Events (no refresh).

```
Desktop browser ──(login, pick mood)──▶  Flask app  ──(SSE push)──▶  Firefox kiosk (the face)
     /control                          on the robot                      /
```

## URLs

| | URL |
|---|---|
| Face (kiosk, on the robot) | `http://localhost:8080/` |
| Control panel (from your desktop) | `http://<robot-ip>:8080/control` |

## Set / change the control-panel password

Until a password is set the panel is **open on the LAN** (with a warning banner).
Set one on the robot:

```bash
ssh user@<robot-ip>
cd ~/robot-face
python3 manage.py set-password          # prompts, hidden input
systemctl --user restart robot-face
```

## Moods & colours

Both are driven by the `<robot-face>` component and defined in `app.py`
(`DEFAULT_MOODS`, `DEFAULT_COLORS`) — the live copy lives in `config.json` on the
robot. Moods map 1:1 to the component's `emotion` attribute:

`auto` (autonomous cycle) · `idle` · `happy` · `curious` · `love` · `thinking` ·
`surprised` · `sleepy` · `sad` · `angry`

Colours: amber `#FFAE1E` · orange `#FF7A1E` · yellow `#FFD34D` · cyan `#2AD4FF`.

## How it runs on the robot (NVIDIA Jetson Orin Nano, Ubuntu 22.04, XFCE)

- **Backend**: a **user** systemd service `robot-face` (`systemctl --user`), so it
  needs no root and starts on login. gdm autologin → the jarvis session → the
  service starts → serves port 8080 on all interfaces.
- **Kiosk**: `~/.config/autostart/robot-face-kiosk.desktop` launches
  `firefox --kiosk http://localhost:8080/` ~8s into the session, using a dedicated
  **GPU-accelerated, crash-hardened** profile at `~/.robotface-ff`.
- **Display**: the panel is physically 1080×1920; the pre-existing
  `rotate-display` autostart rotates it to 1920×1080 landscape and calibrates the
  touchscreen. The face fills whatever viewport it gets.

### GPU acceleration (important)

Firefox blocklists WebRender + accelerated canvas on aarch64/Tegra, so out of the
box it software-rasterizes every frame → laggy. The Orin's GL/EGL stack is fine,
so the kiosk profile (`deploy/firefox-kiosk.user.js`, copied to
`~/.robotface-ff/user.js`) forces it on:

- `gfx.webrender.all`, `gfx.canvas.accelerated`, `gfx.x11-egl.force-enabled`
- launch env: `MOZ_X11_EGL=1 MOZ_WEBRENDER=1`

Result: a real Firefox **GPU process** + a locked **60 fps**. Verify with
`pgrep -af firefox | grep ' gpu'`.

### Renderers (2D vs WebGL)

There are two interchangeable renderers for the `<robot-face>` component, chosen
by `config.json` → `"renderer"`:

- **`"gl"` (default)** — `static/robot-face-gl.js`. WebGL: the whole face is one
  SDF fragment shader with the glow baked in. Guaranteed GPU path; auto-falls
  back to 2D if WebGL is unavailable.
- **`"2d"`** — `static/robot-face.js`. Canvas 2D (GPU-accelerated via
  `gfx.canvas.accelerated`) with a CSS drop-shadow glow. Marginally lighter GPU
  load; exactly matches the imported design source.

Measured on this Orin (30fps, 0.75 scale): 2D ~18% GR3D / ~5.79W board, WebGL
~30% GR3D / ~5.85W. **Total board power is display-dominated (~5.9W either way)**,
so the choice is about robustness/aesthetics, not energy. Flip with:
`python3 manage.py show` isn't for this — edit `config.json` `"renderer"` and
`systemctl --user restart robot-face`. Perf knobs (`RENDER_FPS`, `RENDER_SCALE`)
are at the top of each renderer file.

### Power & smoothness

Total board power is **display-dominated** (~4.8W of ~5.9W is the panel + SoC
baseline, and there's no software backlight control), so the renderer can only
move the remaining ~1W. Applied:

- **GPU forced on** (see above) — the big one; stopped CPU software-rasterizing.
- **Adaptive frame rate** (both renderers) — 60fps only while something moves
  (blinks, saccades, expression changes), ~10fps while holding still. GR3D drops
  to ~0% between motions. Holding an expression ≈ 5.56W vs ~5.85W flat-30fps, and
  motion is *crisper* (60 vs 30). Tune `ACTIVE_FPS`/`IDLE_FPS` atop each renderer.
- **xfwm4 compositing disabled** (`xfconf-query -c xfwm4 -p /general/use_compositing
  -s false`) — removes a per-frame full-screen composite copy for the kiosk (~150mW).

Not applied (needs root / hardware):
- **`nvpmodel`** — the SoC is on `MAXN_SUPER` (uncapped). `sudo nvpmodel -m 0`
  (15W cap) or `-m 3` (7W cap) lowers the whole envelope for this light workload.
- The **panel's own ~4.8W is a hard floor** from software (no backlight interface).

### Screensaver

`xfce4-screensaver` blanks the panel on idle (ignoring `xset`). It's disabled via
`xfconf` (`/saver/enabled=false`) and a `Hidden=true` autostart override.

## Deploy / update

From this project directory on your Mac:

```bash
./deploy/deploy.sh          # rsync + (re)install user service + kiosk autostart
```

Note: templates are cached by Flask, so after changing HTML the deploy restarts
the service; static JS/CSS is picked up on the next Firefox reload.

## Service management (on the robot)

```bash
systemctl --user status robot-face
systemctl --user restart robot-face
journalctl --user -u robot-face -f      # if user journal persistence is enabled
```

## Files

```
app.py                         Flask backend (face, control, auth, SSE, state)
manage.py                      set-password / show CLI
templates/face.html            kiosk face page (loads the component, live SSE)
templates/control.html         mood + colour control panel
templates/login.html           password login
static/robot-face.js           the <robot-face> component (perf-tuned for Jetson)
config.json / state.json       runtime (password hash, secret, current mood) — not in git
deploy/robot-face.service      user systemd unit
deploy/robot-face-kiosk.desktop  kiosk autostart (GPU profile)
deploy/firefox-kiosk.user.js   Firefox prefs: force GPU + kiosk hardening
deploy/deploy.sh               one-command deploy
```
