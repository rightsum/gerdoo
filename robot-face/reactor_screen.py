"""
The reactor screen: Gerdoo's arc-reactor heart on the 1.69" LCD in the front cover.

Seven looks, after the design canvas "Gerdoo arc reactor screens" (claude.ai), drawn
full-screen at 240x280 with numpy:

    boot        segments light round the edge, then the core blooms (once, at start)
    idle        a breathing core inside nested frames, a slow scan line
    listening   frame-shaped ripples out to the edge, a fast-pulsing core
    thinking    a light sweep and two counter-rotating triangles; light chases the edge
    speaking    full-screen voice bars behind a Mark VI triangle
    charging    green energy filling the screen to the battery level, with the percentage
    low         a thin, flickering amber level and the percentage

The 12 edge segments sit at the same angles as the 12 coil pads printed round the
window, so the light carries on from the cover into the screen.

What is shown:
  - robot-face's state.json: "reactor" (an override from the control panel: "auto" or
    a look) and "voice" (idle / connecting / listening / thinking / speaking / error)
  - /tmp/battery_status.json (battery_bridge.py): below LOW_BATTERY percent, "low"
  - charging is not detected yet, so that look only shows as an override

Only what changed is sent, as a few small rectangles, plus one rotating band of rows and
the panel's settings every 2 s so a glitch heals itself: the wires to the header carry
~6 MHz cleanly, where a full frame takes ~180 ms (log 047).

    python3 reactor_screen.py               # the service loop
    python3 reactor_screen.py show thinking 10
"""

import json
import math
import os
import signal
import sys
import time

import numpy as np

W, H = 240, 280
CX, CY = W / 2, H / 2
FPS = 12
BOOT_SECONDS = 3.6
LOW_BATTERY = 15            # percent
POLL_SECONDS = 0.25

BASE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE, "state.json")
BATTERY_FILE = "/tmp/battery_status.json"
STATUS_FILE = "/tmp/reactor_status.json"     # what is on screen now, for the panel

LOOKS = ("boot", "idle", "listening", "thinking", "speaking", "charging", "low")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _hex(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


CYAN, GREEN, AMBER = _hex("38D9FF"), _hex("3CF2A0"), _hex("FFB000")
WHITE = np.ones(3, np.float32)

Y, X = (np.mgrid[0:H, 0:W].astype(np.float32) + 0.5)
DX, DY = X - CX, Y - CY
ANGLE = np.arctan2(DX, -DY) % (2 * math.pi)      # 0 at the top, clockwise


# ---- shapes (signed distances, negative inside) ----

def rrect(cx, cy, hw, hh, r):
    qx = np.abs(X - cx) - (hw - r)
    qy = np.abs(Y - cy) - (hh - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def triangle(R, theta, cx=CX, cy=CY):
    """Equilateral triangle, circumradius R, a vertex up, turned clockwise by theta."""
    c, s = math.cos(theta), math.sin(theta)
    px, py = X - cx, Y - cy
    x = c * px + s * py
    y = -(-s * px + c * py)                  # rotate, then flip to y-up
    r = R * math.sqrt(3) / 2                  # half the side
    k = math.sqrt(3)
    x = np.abs(x) - r
    y = y + r / k
    m = x + k * y > 0
    nx = np.where(m, (x - k * y) / 2, x)
    ny = np.where(m, (-k * x - y) / 2, y)
    nx = nx - np.clip(nx, -2 * r, 0)
    return -np.hypot(nx, ny) * np.sign(ny)


def fill(d):
    return np.clip(0.5 - d, 0, 1)


def stroke(d, w):
    return np.clip(w / 2 + 0.5 - np.abs(d), 0, 1)


def halo(d, s):
    return np.exp(-np.abs(d) / s)


# ---- compositing (float RGB, 0..1) ----

def over(img, color, a):
    img += (color - img) * np.clip(a, 0, 1)[..., None]


def screen(img, color, a):
    img[:] = 1 - (1 - img) * (1 - np.clip(a, 0, 1)[..., None] * color)


def radial(rx, ry, stops, scale=1.0):
    """CSS-like elliptical gradient (farthest corner) -> (colour HxWx3, alpha HxW)."""
    e = np.hypot(DX / (rx * scale), DY / (ry * scale)) / math.sqrt(2)
    pos = [p for p, _, _ in stops]
    col = np.stack([np.interp(e, pos, [c[i] for _, c, _ in stops]) for i in range(3)], -1)
    return col.astype(np.float32), np.interp(e, pos, [a for _, _, a in stops]).astype(np.float32)


def vertical(stops):
    pos = [p * H for p, _ in stops]
    col = np.stack([np.interp(Y[:, :1], pos, [c[i] for _, c in stops]) for i in range(3)], -1)
    return np.broadcast_to(col, (H, W, 3)).astype(np.float32)


# The 12 edge segments, clockwise from the top centre, (x, y, horizontal?).
SEGMENTS = [(120, 13, 1), (193.5, 13, 1), (227, 78, 0), (227, 140, 0), (227, 202, 0),
            (193.5, 267, 1), (120, 267, 1), (46.5, 267, 1), (13, 202, 0), (13, 140, 0),
            (13, 78, 0), (46.5, 13, 1)]
BOTTOM_UP = [6, 5, 7, 4, 8, 3, 9, 2, 10, 1, 11, 0]   # charging fills them in this order


class Reactor:
    def __init__(self):
        d = [rrect(x, y, 14 if h else 3.5, 3.5 if h else 14, 3.5) for x, y, h in SEGMENTS]
        self.seg_core = np.stack([fill(s) for s in d])
        # glow cut off at 16 px: beyond that it is too faint to see but would still change
        # pixels (and cost bytes on the 6 MHz link) whenever a segment brightens
        self.seg_glow = np.stack([(np.exp(-np.maximum(s, 0) / 3.5) * .8 + np.exp(-np.maximum(s, 0) / 7) * .4) * (s > 0) * (s < 16) for s in d])
        self.d_outer = rrect(CX, CY, 107, 127, 26)
        self.d_mid = rrect(CX, CY, 89, 109, 20)
        self.d_in = rrect(CX, CY, 71, 91, 14)
        self.dash = (np.sin(ANGLE * 48) > 0).astype(np.float32)
        self.bg = {}
        for name, g in (("cyan", CYAN), ("green", GREEN), ("amber", AMBER)):
            for k, centre in ((1, .15), (2, .27), (3, .11), (4, .20)):
                col, _ = radial(W / 2, H / 2, [(0, g * centre, 1), (.55, _hex("04121c"), 1), (1, _hex("010407"), 1)])
                self.bg[(name, k)] = col
        self._text = {}
        self._static = {}

    # -- pieces --

    def segments(self, img, glow, k, dark=None):
        k = np.asarray(k, np.float32)
        screen(img, glow, np.tensordot(k, self.seg_glow, 1))
        if dark is not None:
            over(img, dark, np.tensordot(1 - k, self.seg_core, 1))
        over(img, WHITE, np.tensordot(k, self.seg_core, 1))

    def bloom(self, img, glow, rx, ry, scale, alpha, white_to=.16, glow_at=.40, end=.70):
        col, a = radial(rx, ry, [(0, WHITE, 1), (white_to, _hex("effdff"), 1), (glow_at, glow, 1), (end, glow, 0), (2, glow, 0)], scale)
        over(img, col, a * alpha)

    def text(self, lines):
        """[(string, size, y)] -> alpha mask, cached."""
        key = tuple(lines)
        if key not in self._text:
            from PIL import Image, ImageDraw, ImageFont
            im = Image.new("L", (W, H))
            d = ImageDraw.Draw(im)
            for s, size, y in lines:
                d.text((W // 2, y), s, font=ImageFont.truetype(FONT, size), fill=255, anchor="mm")
            self._text[key] = np.asarray(im, np.float32) / 255
            if len(self._text) > 64:
                self._text.pop(next(iter(self._text)))
        return self._text[key]

    def liquid(self, img, t, pct, top, mid, bottom, sky):
        level = H * (1 - max(pct, 4) / 100)
        w1 = level + 5 * np.sin(2 * math.pi * (X[:1] / 160 + t / 3))
        w2 = level - 2 + 3 * np.sin(2 * math.pi * (X[:1] / 100 - t / 2))
        body = vertical([(0, top), (.45, mid), (1, bottom)])
        img[:] = sky
        over(img, body * .7 + sky * .3, np.clip(Y - w2 + .5, 0, 1))
        over(img, body, np.clip(Y - w1 + .5, 0, 1))
        return level

    # -- looks --

    def render(self, look, t, pct=None):
        return getattr(self, "_" + look)(t, pct if pct is not None else 68)

    # The glow and frames of idle/listening/thinking/speaking are drawn once and kept still;
    # only thin or small things move (scan line, core, one frame outline, a comet, short
    # voice bars, single segments). The wires carry ~6 MHz, so a frame that changes the
    # whole screen takes ~180 ms; these change a few percent and run at ~12 fps (log 047).

    def static(self, look):
        if look not in self._static:
            self._static[look] = getattr(self, "_static_" + look)()
        return self._static[look]

    def core_pulse(self, img, level, radius=14, colour=WHITE):
        r = np.hypot(DX, DY)
        screen(img, colour, np.exp(-(r / radius) ** 2) * (r < 2.2 * radius) * level)

    def _static_idle(self):
        img = self.bg[("cyan", 1)].copy()
        self.bloom(img, CYAN, 90, 110, 1.0, .95)
        screen(img, CYAN, .4 * stroke(self.d_outer, 1))
        screen(img, CYAN, (stroke(self.d_mid, 1.5) + .6 * halo(self.d_mid, 5)) * .85)
        screen(img, CYAN, .67 * stroke(self.d_in, 1) * self.dash)
        self.segments(img, CYAN, np.ones(12))
        return img

    def _idle(self, t, pct):
        img = self.static("idle").copy()
        self.core_pulse(img, .2 + .35 * (.5 + .5 * math.sin(2 * math.pi * t / 3.6)))
        p = (t % 5) / 5
        ys = p * 290 - 10
        fade = min(1, p / .1, (1 - p) / .1)
        y0, y1 = max(0, int(ys - 6)), min(H, int(ys + 7))
        if y1 > y0:
            sl = img[y0:y1]
            band = np.exp(-((Y[y0:y1] - ys) / 1.6) ** 2) * np.clip(1 - np.abs(DX[y0:y1]) / 120, 0, 1) * fade
            screen(sl, CYAN, band)
            over(sl, WHITE, band * .6)
        i = int(t / .5) % 12                    # one segment at a time flares
        screen(img, CYAN, self.seg_glow[i] * .7 * math.sin(math.pi * ((t / .5) % 1)))
        return img

    def _static_listening(self):
        img = self.bg[("cyan", 2)].copy()
        self.bloom(img, CYAN, 100, 120, 1.02, 1, white_to=.18, glow_at=.44)
        screen(img, CYAN, (stroke(self.d_mid, 1.5) + .6 * halo(self.d_mid, 5)) * .9)
        self.segments(img, CYAN, np.full(12, .9))
        return img

    def _listening(self, t, pct):
        # rings rising out of the core, kept inside r 64 so only that patch is re-sent
        img = self.static("listening").copy()
        y0, y1, x0, x1 = int(CY - 66), int(CY + 67), int(CX - 66), int(CX + 67)
        sl = img[y0:y1, x0:x1]
        r = np.hypot(DX[y0:y1, x0:x1], DY[y0:y1, x0:x1])
        for k in range(3):
            p = (t / 1.2 + k / 3) % 1
            d = r - (10 + p * 50)
            screen(sl, CYAN, (stroke(d, 2.5) + .6 * halo(d, 3)) * (1 - p) * (r < 64))
        self.core_pulse(img, .25 + .4 * (.5 + .5 * math.sin(2 * math.pi * t / .6)))
        return img

    TRI_R = 100

    def _static_thinking(self):
        img = self.bg[("cyan", 3)].copy()
        self.bloom(img, CYAN, 65, 78, .95, .6)
        d = triangle(self.TRI_R, 0)
        screen(img, CYAN, (stroke(d, 3) + .4 * halo(d, 5)) * .45)
        screen(img, CYAN, .33 * stroke(self.d_outer, 1))
        self.segments(img, CYAN, np.full(12, .15))
        return img

    def _thinking(self, t, pct):
        img = self.static("thinking").copy()
        # a comet running round the triangle, with a short tail
        v = [(CX + self.TRI_R * math.sin(a), CY - self.TRI_R * math.cos(a)) for a in (0, 2 * math.pi / 3, 4 * math.pi / 3)]
        for j, lag in enumerate((0, .04, .08, .12)):
            u = ((t / 1.8 - lag) % 1) * 3
            e = int(u)
            f = u - e
            (ax, ay), (bx, by) = v[e], v[(e + 1) % 3]
            px, py = ax + (bx - ax) * f, ay + (by - ay) * f
            x0, x1, y0, y1 = int(px - 14), int(px + 15), int(py - 14), int(py + 15)
            x0, y0 = max(0, x0), max(0, y0)
            sl = img[y0:y1, x0:x1]
            r = np.hypot(X[y0:y1, x0:x1] - px, Y[y0:y1, x0:x1] - py)
            k = (1, .55, .3, .15)[j]
            screen(sl, CYAN, np.exp(-(r / 6) ** 2) * k)
            over(sl, WHITE, np.exp(-(r / 3) ** 2) * k)
        phase = ((t - np.arange(12) * .1) % 1.2) / 1.2
        k = np.interp(phase, [0, .06, .26, 1], [.15, 1, .15, .15])
        screen(img, CYAN, np.tensordot(k - .15, self.seg_glow, 1))
        over(img, WHITE, np.tensordot(k - .15, self.seg_core, 1))
        self.core_pulse(img, .15 + .2 * (.5 + .5 * math.sin(2 * math.pi * t / 1.2)))
        return img

    # four short voice bars either side of the triangle
    BAR_X = (12, 23, 34, 45, 195, 206, 217, 228)
    BAR_H = (60, 90, 120, 150, 150, 120, 90, 60)

    def _static_speaking(self):
        img = self.bg[("cyan", 4)].copy()
        d = triangle(85, 0)
        over(img, CYAN, fill(d))
        screen(img, CYAN, .5 * halo(np.maximum(d, 0), 6) * (d > 0))
        d2 = triangle(74, 0)
        u = np.clip(np.hypot(DX / 74, (DY - 8) / 74), 0, 1)[..., None]
        inner = WHITE * (1 - u) ** .6 + _hex("0b3a50") * (1 - (1 - u) ** .6)
        over(img, inner, fill(d2))
        screen(img, CYAN, .4 * stroke(self.d_outer, 1))
        return img

    def _speaking(self, t, pct):
        img = self.static("speaking").copy()
        for i, (xc, h) in enumerate(zip(self.BAR_X, self.BAR_H)):
            period = .36 + .13 * ((i * 7) % 5) / 4
            k = .12 + .88 * (.5 - .5 * math.cos(2 * math.pi * t / period + i * 1.7))
            half = h * k / 2
            x0, x1 = int(xc - 5), int(xc + 6)
            y0, y1 = max(0, int(CY - half - 1)), min(H, int(CY + half + 2))
            sl = img[y0:y1, x0:x1]
            u = np.abs(DY[y0:y1, x0:x1]) / max(half, 1)
            inside = np.clip(3.5 + .5 - np.abs(X[y0:y1, x0:x1] - xc), 0, 1) * (u < 1)
            col = WHITE * (1 - u)[..., None] + CYAN * u[..., None]
            over(sl, col, inside * np.clip(1.6 - 1.6 * u, 0, 1))
        self.core_pulse(img, .2 + .4 * (.5 + .5 * math.sin(2 * math.pi * t / .45)), radius=16)
        return img

    def _charging(self, t, pct):
        img = np.zeros((H, W, 3), np.float32)
        level = self.liquid(img, t, pct, GREEN * .67, GREEN * .33, _hex("0b3a28"), _hex("021009"))
        for x, period, off, r in ((45, 3, 0, 2.5), (105, 3.6, .9, 1.8), (165, 2.8, 1.6, 2.2), (200, 3.3, 2.2, 1.5)):
            p = ((t + off) % period) / period
            y = H - 20 - p * (H - 20 - level)
            a = np.clip(r + .5 - np.hypot(X - x, Y - y), 0, 1) * min(1, p / .2) * (1 - p)
            over(img, _hex("eafff5"), a * .9)
        over(img, WHITE, self.text([(f"{pct}%", 74, 138), ("CHARGING", 15, 186)]))
        screen(img, GREEN, .53 * stroke(self.d_outer, 1))
        lit = int(round(pct / 100 * 12))
        k = np.zeros(12, np.float32)
        for n, i in enumerate(BOTTOM_UP):
            if n < lit:
                k[i] = 1
            elif n == lit:
                k[i] = .2 + .8 * (.5 + .5 * math.sin(2 * math.pi * t / 1.4))
        self.segments(img, GREEN, k, dark=_hex("12261d"))
        return img

    def _low(self, t, pct):
        img = np.zeros((H, W, 3), np.float32)
        self.liquid(img, t / 2, max(pct, 6), AMBER * .8, AMBER * .55, AMBER * .35, _hex("0c0602"))
        over(img, AMBER, self.text([(f"{pct}%", 74, 128), ("LOW POWER", 15, 178)]))
        cyc = (t % 3.2) / 3.2
        flicker = .3 if .41 <= cyc < .43 else .25 if .69 <= cyc < .71 else 1
        img *= flicker
        screen(img, AMBER, .33 * stroke(self.d_outer, 1))
        k = np.zeros(12, np.float32)
        k[6] = .25 + .75 * (.5 + .5 * math.cos(2 * math.pi * t))
        self.segments(img, AMBER, k, dark=_hex("2a1a0c"))
        return img

    def _boot(self, t, pct):
        img = np.zeros((H, W, 3), np.float32) + _hex("010407")
        bg_in = np.clip((t - 2.0) / .4, 0, 1)
        if bg_in:
            over(img, self.bg[("cyan", 1)], np.full((H, W), bg_in, np.float32))
        k = np.clip((t - np.arange(12) * .14) / .1, 0, 1)
        if t >= 1.6:
            sc = 1.15 - .15 * min(1, (t - 1.6) / .4)
            a = min(1, (t - 1.6) / .4)
            d = rrect(CX, CY, 89 * sc, 109 * sc, 20 * sc)
            screen(img, CYAN, (stroke(d, 1.5) + .6 * halo(d, 5)) * a)
        if t >= 2.1:
            u = min(1, (t - 2.1) / .4)
            sc = .1 + 1.15 * u if u < 1 else 1.25 - .25 * min(1, (t - 2.5) / .4)
            self.bloom(img, CYAN, 90, 110, max(sc, .1), min(1, u * 2))
        self.segments(img, CYAN, k)
        return img


# ---- what to show ----

def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def battery_percent():
    """The UPS battery, and the main pack once its voltage sensor reads anything (it read 0 V
    while unwired): the lower of the two. None if neither is known."""
    b = _read_json(BATTERY_FILE)
    vals = []
    for key, connected in (("jetson_battery", 0), ("main_battery", 6)):
        v = b.get(key) or {}
        if v.get("percent") is not None and (v.get("voltage") or 0) > connected:
            vals.append(int(v["percent"]))
    return min(vals) if vals else None


def choose():
    st = _read_json(STATE_FILE)
    pct = battery_percent()
    override = st.get("reactor", "auto")
    if override in LOOKS and override != "auto":
        return override, pct
    voice = st.get("voice", "idle")
    if voice in ("connecting", "listening"):
        return "listening", pct
    if voice in ("thinking", "speaking"):
        return voice, pct
    if pct is not None and pct < LOW_BATTERY:
        return "low", pct
    return "idle", pct


def to565(img):
    a = (np.clip(img, 0, 1) * 255 + .5).astype(np.uint16)
    return ((a[..., 0] >> 3) << 11) | ((a[..., 1] >> 2) << 5) | (a[..., 2] >> 3)


def changed_box(prev, cur):
    """Inclusive (x0, y0, x1, y1) of the pixels that differ, or None."""
    if prev is None:
        return 0, 0, W - 1, H - 1
    diff = prev != cur
    rows, cols = np.flatnonzero(diff.any(1)), np.flatnonzero(diff.any(0))
    if not len(rows):
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1])


TILE = 8
MAX_RECTS = 12
# A rectangle costs ~3 ms to set up (6 small SPI calls at ~0.3 ms each); bulk pixels cost
# ~2.7 us each at 6 MHz. So two rectangles are worth joining while the pixels the join adds
# cost less than one set-up: about 1100 pixels (measured 2026-10-29, log 047).
JOIN_WASTE_PX = 1100


def changed_rects(prev, cur, tile=TILE, max_rects=MAX_RECTS):
    """The changed pixels as a few inclusive (x0, y0, x1, y1) rectangles, on an 8 px grid.

    Changed tiles form runs along each tile row (one-tile gaps bridged); a run joins the
    rectangle above it when both edges line up within two tiles, so a frame outline comes out
    as its sides and a moving dot as one square (a wide run must not swallow two narrow ones). Then the pair whose
    join wastes least is merged while that waste is cheaper than a window set-up, or while
    there are more than max_rects."""
    if prev is None:
        return [(0, 0, W - 1, H - 1)]
    d = (prev != cur).reshape(H // tile, tile, W // tile, tile).any(axis=(1, 3))
    done, live = [], []                       # rects as [r0, r1, c0, c1] in tiles
    for r in range(d.shape[0]):
        runs = []
        for c in np.flatnonzero(d[r]):
            if runs and c - runs[-1][1] <= 2:
                runs[-1][1] = int(c)
            else:
                runs.append([int(c), int(c)])
        nxt = []
        for c0, c1 in runs:
            hit = [b for b in live if abs(c0 - b[2]) <= 2 and abs(c1 - b[3]) <= 2]   # edges line up
            if hit:
                for b in hit:
                    live.remove(b)
                m = [min(b[0] for b in hit), r, min([c0] + [b[2] for b in hit]), max([c1] + [b[3] for b in hit])]
            else:
                m = [r, r, c0, c1]
            nxt.append(m)
        done += live
        live = nxt
    done += live
    area = lambda b: (b[1] - b[0] + 1) * (b[3] - b[2] + 1) * tile * tile
    while len(done) > 1:
        best = None
        for i in range(len(done)):
            for j in range(i + 1, len(done)):
                a, b = done[i], done[j]
                u = [min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3])]
                waste = area(u) - area(a) - area(b)
                if best is None or waste < best[0]:
                    best = (waste, i, j, u)
        if best[0] > JOIN_WASTE_PX and len(done) <= max_rects:
            break
        _, i, j, u = best
        done = [b for k, b in enumerate(done) if k not in (i, j)] + [u]
    return [(c0 * tile, r0 * tile, (c1 + 1) * tile - 1, (r1 + 1) * tile - 1) for r0, r1, c0, c1 in done]


REFRESH_ROWS = 8             # rows re-sent per frame regardless of change: a glitch heals within ~3 s
CONFIG_EVERY = 2.0           # seconds between re-sending the panel's settings


def run(fixed=None, seconds=None):
    import lcd169
    lcd = lcd169.LCD()
    r = Reactor()
    stop = []
    signal.signal(signal.SIGTERM, lambda *a: stop.append(1))
    signal.signal(signal.SIGINT, lambda *a: stop.append(1))
    start = time.time()
    look, since = (fixed or "boot"), start
    pct, next_poll, prev = None, 0, None
    band, next_config = -REFRESH_ROWS, 0
    status = None
    try:
        while not stop and (seconds is None or time.time() - start < seconds):
            now = time.time()
            if now >= next_poll:
                next_poll = now + POLL_SECONDS
                want, pct = choose()
                if fixed:
                    want = fixed
                elif look == "boot" and now - since < BOOT_SECONDS:
                    want = "boot"
                if want != look:
                    look, since = want, now
                if status != (look, pct):
                    status = (look, pct)
                    tmp = STATUS_FILE + ".tmp"
                    with open(tmp, "w") as f:
                        json.dump({"look": look, "battery": pct, "updated": now}, f)
                    os.replace(tmp, STATUS_FILE)
            cur = to565(r.render(look, now - since, pct if pct is not None else 68))
            rects = changed_rects(prev, cur)
            band = (band + REFRESH_ROWS) % H
            rects.append((0, band, W - 1, min(H, band + REFRESH_ROWS) - 1))
            if now >= next_config:
                next_config = now + CONFIG_EVERY
                lcd.refresh_config()
            for x0, y0, x1, y1 in rects:
                lcd.show_region(x0, y0, x1, y1, cur[y0:y1 + 1, x0:x1 + 1].astype(">u2").tobytes())
            prev = cur
            time.sleep(max(0, 1 / FPS - (time.time() - now)))
    finally:
        lcd.show(np.zeros((H, W), ">u2").tobytes())
        lcd.close()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "show" and sys.argv[2] in LOOKS:
        run(sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 10)
    elif len(sys.argv) == 1:
        run()
    else:
        print(__doc__)
