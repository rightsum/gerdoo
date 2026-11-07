# 047 — The reactor screen: the 1.69" LCD on the Jetson's header

| | |
|---|---|
| **Date** | 2026-10-29 |
| **Type** | Bring-up + feature |
| **Status** | ✅ Wired, 6 MHz with self-repair, 11–21 fps · ✅ `reactor-screen` user service, 7 looks, follows the voice state and battery · ✅ Panel card "Reactor screen" · ✅ 223 tests pass · ⏳ Charging can't be detected yet (manual from the panel) |
| **Severity** | — |

---

## What it is

The 1.69" Waveshare LCD (ST7789V2, 240×280) behind the front cover's arc reactor becomes the robot's "heart".

**Design:** the canvas "Gerdoo arc reactor screens" on Claude Design. It went through three rounds with the user:
1. A drawn reactor with casing and coils.
2. Just the core, because the gold ring and coil pads are already printed on the cover.
3. **Full screen, not circular:** rounded-rectangle frames, and the 12 light segments on the screen's edge at the angles of the cover's 12 coil pads.

**The seven looks:**

| Look | What it shows |
|---|---|
| boot | Segments light round the edge, then the core blooms |
| idle | A breathing core, nested frames, a slow scan line |
| listening | Frame-shaped ripples, a fast core |
| thinking | A light sweep, two counter-rotating triangles, light chasing round the edge |
| speaking | Full-screen voice bars behind a Mark VI triangle |
| charging | A green energy level with the percentage; the segments fill bottom-up |
| low | A flickering amber level and the percentage |

## Wiring: the Jetson, not the XIAO

Log 030 planned to drive the screen from the XIAO ESP32S3 on the reSpeaker core board. **Changed:**
- Seeed's wiki, Flex wiki and CNX article don't say which XIAO pins the XVF3800 board leaves free.
- The Jetson already holds the robot's state.

| Display | Header pin | Function |
|---|---|---|
| VCC | 17 | 3.3 V |
| GND | 20 | |
| DIN | 19 | SPI1 MOSI (`spi1_mosi_pz5`), `/dev/spidev0.0` = `3210000.spi` |
| CLK | 23 | SPI1 SCK (`pz3`) |
| CS | 24 | SPI1 CS0 (`pz6`) |
| DC | 29 | `soc_gpio32_pq5`, gpiochip0 line 105 |
| RST | 31 | `soc_gpio33_pq6`, line 106 |
| BL | 32 | `soc_gpio19_pg6`, line 41 |

The pin-to-pad map comes from NVIDIA's own `tegra234-p3767-0000+p3509-a02-hdr40.dtbo`.

## Three things that got in the way

**1. `-o dtbo` doesn't apply anything.**
- `config-by-function.py -o dtbo spi1` only writes `/boot/jetson-io-hdr40-user-custom.dtbo`.
- `-o dt 1="spi1"` is the form that adds a `JetsonIO` entry with `OVERLAYS` to extlinux.conf and makes it the default. The old `primary` entry stays as the fallback.

**2. The header GPIOs were tristated.**
- Symptom: SPI worked, but the screen showed only the backlight, then static.
- debugfs `pinconf-groups` showed `tristate=1, enable-input=1` on pq5, pq6 and pg6. The output drivers were off, so DC, RST and BL never moved.
- That is JetPack 6's default for these header pins.
- **Fix:** the jetson-io overlay was decompiled and nodes for pins 29/31/32 were added (`tristate=0, enable-input=0, pull=0`, functions `rsvd0`/`rsvd1` as the pads already had). It was recompiled and installed over the same file. The SPI-only version is kept as `/boot/jetson-io-hdr40-user-custom.dtbo.spi-only.bak`.
- ⚠️ **If jetson-io is ever run again, it rewrites this file and the three GPIOs go back to tristate.** Re-add the nodes; the source is `/tmp/gerdoo-hdr40.dts` (lost on reboot), or decompile the installed file.

**3. The jumper wires only carry 8 MHz.**

| Speed | Result |
|---|---|
| 2, 4, 6, 8 MHz | Clean |
| 10, 12, 16, 20, 40 MHz | TV static |

- A full frame takes ~160 ms at 8 MHz.
- So the renderer sends only the rectangle that changed since the last frame. The screen updates about 6–12 times a second, depending on the look.
- A GND wire twisted around CLK, or shorter wires, should raise the limit.

## Software (`robot-face/`)

**`lcd169.py`:**
- ST7789V2 driver: Waveshare's init for this panel, a 20-row RAM offset, `show_region()`.
- The GPIOs go through the v1 character-device ioctls. `Jetson.GPIO` can't identify this board ("Could not determine Jetson model"), and the libgpiod Python bindings aren't installed.
- `python3 lcd169.py test` shows colour bars and an orientation card.

**`reactor_screen.py`:**
- **Drawing:** signed-distance shapes in numpy. Render times per frame:

  | Look | ms |
  |---|---|
  | boot | 7 |
  | idle | 23 |
  | listening | 25 |
  | thinking | 33 |
  | speaking | 20 (78 before each bar was limited to its own columns) |
  | charging | 27 |
  | low | 20 |

- **Choosing the look:**
  - the `reactor` override in `state.json`;
  - otherwise the voice state (connecting/listening → listening; thinking; speaking);
  - otherwise **low** below 15% battery;
  - otherwise idle.
- **Battery:** the UPS percentage from `/tmp/battery_status.json`. The main pack counts only once its sensor reads more than 6 V; it read 0 V while unwired.
- **Status:** it writes `/tmp/reactor_status.json` for the panel.
- `python3 reactor_screen.py show <look> <seconds>` is for testing.

**The rest:**
- **Service:** `deploy/reactor-screen.service`, installed and restarted by `deploy.sh`.
- **Panel:** `GET/POST /api/reactor` (session tier). The "Reactor screen" card has Auto plus the 7 looks, and shows what is on screen.
- **Tests:** `tests/test_reactor.py`, 21 tests:
  - look choice;
  - the unwired-sensor case;
  - every look draws a valid frame;
  - the changed rectangle;
  - the routes.

## Laggy, then glitchy: living within ~6 MHz (same day)

**What the user saw:**
- At 8 MHz, streaming went to static now and then. Single frames had been clean.
- At 4 MHz it was clean but "soooo laggy": idle changed 97% of the screen every frame, about 3 fps.

**Why it can't simply go faster:**
- The dev kit's 40-pin header runs through auto-direction level shifters, which are weak drivers. Long jumpers on them limit the clock.
- NVIDIA forum reports on the Orin Nano agree: one measured MOSI never reaching 3.3 V; another hit a 20 MHz ceiling even on short wiring.
- The user chose to keep this wiring and make the software fit it.

**Measured on this setup:**

| What | Cost |
|---|---|
| One window set-up | 3.05 ms (each small SPI call ~0.29 ms) |
| One GPIO set | 0.005 ms |
| A 64 KB block at 6 MHz | 94.5 ms (87.4 ms of pure wire time) |

**What changed:**
1. **6 MHz** instead of 8, for margin.
2. **The big glows are drawn once and kept still.** Motion moves into small or thin things:

   | Look | What moves |
   |---|---|
   | idle | Core pulse (r ≤ 31 px), scan line, one flaring segment |
   | listening | Rings rising inside the core (r ≤ 64) |
   | thinking | A comet round a still triangle, a segment chase, core pulse |
   | speaking | 8 short voice bars beside the still triangle |

3. **Segment glow cut off at 16 px.** Faint glow that's invisible still changes pixels, and those pixels cost bytes.
4. **Changes go out as a few rectangles on an 8 px grid.**
   - A run joins the rectangle above only when both edges line up. The first version let a wide run swallow two narrow ones, and the whole screen went out every frame.
   - Two rectangles merge only while the extra pixels cost less than one window set-up (about 1100 px).
5. **Self-repair:**
   - one band of 8 rows is re-sent every frame, so the whole picture is refreshed every ~3 s;
   - the panel's settings (colour format, scan order, inversion, normal mode, wake, display on) are re-sent every 2 s.

   A corrupted byte now heals itself instead of leaving static.

**Result** (frames per second / KB per frame):

| Look | fps | KB |
|---|---|---|
| idle | 21 | 17 |
| listening | 15 | 33 |
| thinking | 11 | 41 |
| speaking | 14 | 35 |
| charging | 14 | 15 |
| low | 16 | 21 |

The user had found speaking (13 fps) and the looks after it fine. Tests: 224 pass, including the rectangle logic (a dot is one square; an outline goes out as its sides, under 25% of the screen, with nothing left out).

## Still open

- **Charging detection.** Nothing measures the charge current yet, so charging shows only from the panel.
- **Orientation.** The test card was shown, but the user hasn't confirmed TOP/left/right on the mounted screen. A 180° flip is a one-line change.
- **Faster SPI** with better wiring.
