# 002 — USB topology, powered hub, and the Teensy/Jetson peripheral split

| | |
|---|---|
| **Date** | 2026-08-04 |
| **Type** | Design decision record (not a fault) |
| **Status** | ✅ Decided — two items pending hardware arrival |
| **Supersedes** | The lidar-on-Teensy wiring in `inventory.md` |
| **Hardware** | Jetson Orin Nano (`jarvis`), YAHBOOM 4-port powered hub, RPLIDAR C1, 2× OV9281, 5.5" AM-OLED, USB speaker |

---

## Question that started it

Which peripherals hang off the Teensy 4.1 co-processor, which off the Jetson, and how do they fit on the USB bus? Working assumption going in was *"delegate all sensors to the co-processor, keep AI and image processing on the Jetson."*

That assumption is right in outline and wrong in one specific place.

## The principle

**A microcontroller earns its place by timing determinism, not by offloading CPU.**

Linux is not a realtime OS. The scheduler can pause a process for 5–100 ms with no warning — a disk flush, a network interrupt, the AI model allocating. Invisible for most work, fatal for some:

- 20 kHz PWM means flipping a pin every 25 µs, forever, never late.
- An encoder edge missed is position error that **accumulates permanently** — it never washes out.
- HC-SR04 encodes distance *as pulse width*: 58 µs = 1 cm. A 5 ms scheduling delay is 86 cm of error.

The MCU has no OS and no scheduler, so it is never late. That is the entire reason it exists in the design.

**The test for every peripheral is therefore: does anything here have to happen at an exact microsecond?** Not "is it a sensor?"

### Applied

| Device | Timing-critical work | Owner |
|---|---|---|
| Motor PWM | 20 kHz waveform, exact duty | **Teensy** — mandatory |
| Wheel encoders | every edge, thousands/sec, errors accumulate | **Teensy** — mandatory (4 hardware quadrature decoders count in silicon, zero CPU) |
| HC-SR04 | echo pulse width *is* the measurement | **Teensy** — mandatory |
| Servos via PCA9685 | none — the PCA9685 generates pulses itself, host just sends I2C setpoints | Teensy, for tidiness |
| Lights | on/off, brightness | Teensy, for tidiness |
| Weather sensor | one reading every few seconds | Teensy, for tidiness |
| **RPLIDAR C1** | **already done, inside the lidar** | **Jetson — reversal, see below** |

### Corollary worth keeping

Offloading to the Teensy **does not save meaningful Jetson CPU.** The Orin Nano has 6 cores; the lidar driver costs ~3% of one. Nothing is being protected. Use the MCU for *determinism*, not for *load* — that reframe answers every future "which side?" question without re-deriving it.

## Decision 1 — lidar moves to the Jetson (reverses `inventory.md`)

The C1 contains its own microcontroller. It fires the laser, times the return, tracks rotor angle, and hands over **finished measurements**. The delegation already happened at the factory. Putting the Teensy in between makes it a middleman copying bytes.

Three concrete costs to the Teensy path:

1. **It degrades the realtime path.** ~40 KB/s of scan data would cross the same link as motor commands — adding jitter to the one thing that most needs determinism, in service of a device that needs none.
2. **It discards a driver already owned.** `~/ros2_ws/src/rplidar_ros` 2.1.4 ships `rplidar_c1_launch.py` for this exact model, defaulting to `/dev/ttyUSB0` @ 460800. It handles protocol, health monitoring, motor control, and publishes proper `LaserScan`. Reimplementing in firmware is weeks of work for a worse result.
3. **Timestamps.** SLAM accuracy depends on knowing when each scan happened. lidar → Teensy → Jetson timestamps later and less predictably than lidar → Jetson.

**Decision: C1 USB adapter straight into a Jetson port.**

### What this deletes

| Item | Effect |
|---|---|
| Open item **B5** (measure lidar TX ≤ 3.6 V) | **Deleted** — never touches the Teensy |
| MINI560 #1 (dedicated quiet 5V rail) | **Freed** — USB adapter powers the lidar |
| 150 mV ripple constraint | **Gone** — was the reason the rail had to be dedicated |
| Teensy `Serial1` | **Freed** |
| Series resistor on lidar TX | **Not needed** |

One fewer converter, one fewer measurement, one fewer failure mode.

## Decision 2 — the screen is HDMI, not USB

The 5.5" AM-OLED 1920×1080 is **HDMI + driver board**. Video does not consume a USB port. USB is needed only for driver-board power, and for touch if used. A DP→HDMI adapter is already in inventory.

This dissolved the original "screen or lidar for the last port" question — they were never competing.

## Decision 3 — port budget is 7, not 4

The powered hub occupies one Jetson port and returns four. **Net +3.**

```
Jetson 4× USB-A
  ├─ port 1 → YAHBOOM powered hub (9–24V) ─┬─ screen power/touch
  │                                        ├─ speaker
  │                                        ├─ camera?  (see Decision 5)
  │                                        └─ spare
  ├─ port 2 → RPLIDAR C1        (direct — see Decision 4)
  ├─ port 3 → free
  └─ port 4 → free

USB-C device port → l4tbr0 / 192.168.55.1  ← SSH fallback, see log 001
```

Four devices, three spare. Ports were never the constraint — bandwidth is (Decision 5).

## Decision 4 — lidar gets a direct port, not the hub

The hub is externally powered (9–24 V), so it *can* supply the C1's 800 mA cold-start surge — the earlier warning about hubs applies to *unpowered* ones.

But the hub feeds off the 12 V battery, which **sags every time the motors pull current**, and the C1 is the single device least tolerant of that. Per its datasheet it **shuts down the laser and stops scanning on low input power**, and that presents as a *driver fault*, not a power fault — an evening lost to debugging ROS before suspecting the rail.

Three ports are free. Give it one, off the carrier board's own regulator.

Also: short cable. Voltage drop eats the ±4 % window (4.8–5.2 V).

## Decision 5 — camera bandwidth is the real constraint

### Discovered topology

```
Bus 01 (480M,   USB 2.0) → Realtek 4-port hub → ALL four Type-A ports
Bus 02 (10000M, USB 3.0) → Realtek 4-port hub → same four ports
```

Both internal hubs report `bMaxPower=0mA` — self-powered from the carrier board.

**Every Type-A port shares a single USB 2.0 root bus.** Moving a USB 2.0 device between physical ports changes nothing. Neither does putting it on the external hub. There is no second USB 2.0 bus to split across.

### The camera (module S1M03, sold as OV9281)

| Spec | Value |
|---|---|
| Interface | **USB 2.0** |
| Output formats | **MJPEG only** |
| Max transfer | 1280×720 @ 120 fps · 640×400 @ 210 fps · 640×360 @ 210 fps |
| Power | **920 mW max** (~184 mA @ 5V) |
| Supply | USB bus power, 5V ±5% |
| Sensor | 1/4", 3.0 µm pixels, global shutter, fixed focus |
| S/N · dynamic range | 36 dB · 68 dB |
| IR filter | 650 ±10 nm |

### Bandwidth

MJPEG-only is what makes this feasible. Raw 720p120 mono would be ~110 MB/s per camera — impossible on USB 2.0.

```
720p mono JPEG  ≈ 40 KB
120 fps × 40 KB ≈ 4.8 MB/s   per camera
two cameras     ≈ 9.6 MB/s  ≈ 77 Mbps
USB 2.0 usable  ≈ 35 MB/s
```

Throughput is a quarter of the bus. Fine.

### But throughput is not what fails

UVC cameras reserve **isochronous** bandwidth at enumeration from their *declared endpoint size*, not from actual use. A camera consuming 38 Mbps commonly reserves 150–190 Mbps. Two of those against USB 2.0's ~384 Mbps isochronous ceiling sits right at the edge, and failure looks like:

```
Not enough bandwidth for new device state
```

Each camera enumerates fine alone; the second refuses in combination.

### The fix — `UVC_QUIRK_FIX_BANDWIDTH`

Verified present on this kernel: `uvcvideo` 1.1.1, `/lib/modules/5.15.148-tegra/`, exposes `quirks` (currently `4294967295` = `-1` = not overridden).

```bash
# test live (module currently refcount 0, unloads cleanly)
sudo modprobe -r uvcvideo && sudo modprobe uvcvideo quirks=128
cat /sys/module/uvcvideo/parameters/quirks     # expect 128

# persist
echo "options uvcvideo quirks=128" | sudo tee /etc/modprobe.d/uvcvideo.conf
```

`128` = `0x80` = `UVC_QUIRK_FIX_BANDWIDTH`. It makes the driver size the reservation from `dwMaxPayloadTransferSize` — the value negotiated for the format actually selected — and pick the smallest alternate setting that fits.

**Why this matters more than it looks:** without the quirk, lowering resolution or frame rate **barely reduces the reservation**, because the reservation comes from the declared maximum. That is why the failure feels irrational — you turn the settings down and it still refuses to enumerate. The quirk is what makes every other mitigation work. It comes first, not last.

**Trade-off:** MJPEG frame size varies with scene complexity. A cluttered high-contrast view compresses worse than a blank wall. If a frame exceeds what the smaller alt setting carries, frames drop or tear. It shows up as *intermittent corruption under visual load*, not a clean error. `nodrop=1` retains incomplete frames for diagnosis — a diagnostic, not a fix.

### Also true

MJPEG-only means the Jetson CPU-decodes every frame, and JPEG artifacts sit between the global shutter and any precision vision work. Fine for detection; relevant for stereo depth.

## Power budget

Pack: 3S Samsung INR21700-50E, 5000 mAh ≈ **54 Wh**.

| Load | Power | Per hour |
|---|---|---|
| Jetson Orin Nano | 7–25 W (15 W typical) | dominant |
| Screen (est.) | **3–5 W — UNVERIFIED** | ~7 % |
| Lidar | 1.15 W run · 4 W surge | ~2 % |
| Cameras (2×) | 1.84 W | ~3 % |
| Teensy | ~0.5 W | trivial |
| Motors | amps under load | the real drain |

Nothing on USB is a power problem. The Jetson uses 13× the lidar; motors dwarf everything. The screen is the only USB-side load worth a switch — consider leaving it off during autonomous runs.

## Follow-ups

| Action | When |
|---|---|
| Set `quirks=128` **before** first plugging the cameras in | Before cameras arrive |
| Plug both cameras, check `dmesg` for bandwidth errors | On arrival |
| If the second refuses: step one down to 640×400 — *now* effective, with the quirk on | If needed |
| Measure screen power draw (new open item **B7**) | On arrival |
| Update `inventory.md`: lidar → Jetson; camera sensor 1/8" → **1/4"**; add USB 2.0 + MJPEG-only + 920 mW | Next inventory pass |
| Delete open item **B5**; mark MINI560 #1 spare | Next inventory pass |

## Takeaways

1. **MCU for determinism, not for load.** The single reframe that settles every "which side?" question.
2. **A USB peripheral with its own MCU has already delegated.** Adding another co-processor in front of it is pure middleman.
3. **Check the bus topology before the port count.** Four physical ports sharing one USB 2.0 root is not four independent ports.
4. **Isochronous reservation ≠ throughput.** Bandwidth failures happen at enumeration, on declared maxima, not on real traffic.
5. **Reusing a maintained driver beats reimplementing in firmware**, every time — `rplidar_ros` was already sitting in the workspace.

## Related

- [001](001-2026-08-04-jetson-wifi-unreachable.md) — the USB-C fallback link (`192.168.55.1`) referenced in the topology diagram
- `003` — Teensy RawHID / no `/dev/ttyACM*` (open)
- [`../ACTION-PLAN.md`](../ACTION-PLAN.md) · [`../inventory.md`](../inventory.md)
