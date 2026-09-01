- # 🤖 Robot Project — AliExpress Inventory

> **Brain:** NVIDIA Jetson Orin Nano Super (see below)
> **Co-processor:** Teensy 4.1 (see below)
> **WiFi:** Bingfu WLAN Antenna Set (see below)
> **Storage:** Crucial P310 1TB NVMe SSD (see Brain section)
> **Servo Controller:** PCA9685 16-Channel PWM Driver (see Servos & Motor Control)
> **Navigation:** RPLIDAR C1 360° LiDAR (see Navigation & LiDAR)
> **Batteries:** Samsung 21700 cells (see Power & Battery)
> **Wiring reference:** this file. `PINOUT.md` documents the legacy Arduino Nano build and is **stale** — do not use it for the Teensy 4.1 wiring.
> **Decisions and bring-up write-ups:** [`logs/`](logs/README.md) · **Scheduled work:** [`ACTION-PLAN.md`](ACTION-PLAN.md)

---

## 🔑 Access — how to reach the robot

Two independent paths. **The USB one survives every wifi failure** and needs no router — it is the way back in when the network drops.

| Path | Address | Notes |
|---|---|---|
| **Wifi** | `ssh user@<robot-ip>` | SSID `<your-ssid>`, iface `wlP1p1s0`, MAC `<jetson-wifi-mac>`. Key auth; **sudo needs a password** |
| **USB gadget** | `ssh user@192.168.55.1` | Mac side `192.168.55.100` on `en21`. ~1.2 ms. Independent of wifi, DHCP and the router |
| **Serial console** | `/dev/cu.usbmodem*` on the Mac | Last resort if networking is entirely gone |

⚠️ **Wifi power save must stay disabled.** Ubuntu ships `wifi.powersave = 3`; the Realtek `rtl88x2ce` then stops answering inbound packets while idle — the box can reach you but you cannot reach it. Set to `2` in `/etc/NetworkManager/conf.d/default-wifi-powersave-on.conf`. Verify: `iw dev wlP1p1s0 get power_save` → `off`. See [`logs/001`](logs/001-2026-08-04-jetson-wifi-unreachable.md).

### Stable device paths — never hardcode `/dev/ttyACM<N>` or `/dev/ttyUSB<N>`

Both move. Observed shifting `0 → 1 → 0` with nothing unplugged, purely from USB re-enumeration.

```
teensy console    /dev/serial/by-id/usb-Teensyduino_Dual_Serial_19627940-if00
teensy micro-ROS  /dev/serial/by-id/usb-Teensyduino_Dual_Serial_19627940-if02
lidar             /dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_ec8fc9bc95d5ef11afac704b49d2c684-if00-port0
brio 500 camera   /dev/v4l/by-id/usb-046d_Brio_500_2437ZBD0PNK8-video-index0
```

The Brio claims **two** `/dev/video*` nodes — `index1` is metadata, not capture. Use `index0`.

These are keyed on each device's own serial number, so they also disambiguate boards once the arm Teensy is added.

### Services running on the Jetson

| Unit | Purpose |
|---|---|
| `systemctl --user status micro-ros-agent` | Teensy ↔ ROS 2 bridge. `Restart=always` ([`logs/007`](logs/007-2026-08-04-microros-bringup.md)) |
| `systemctl --user status robot-face` | kiosk face on the 5.5" panel, **plus the `/control` panel** — mood, eye colour, camera stream, live LiDAR view ([`logs/006`](logs/006-2026-08-04-robot-face-adoption.md), [`logs/008`](logs/008-2026-08-04-control-panel-camera-lidar.md)) |
| `systemctl --user status rplidar` | lidar driver + `/scan` bridge. **On demand only** — `static` unit, started by the control panel, never at boot |

> The panel is **owned by the kiosk**, full-screen. It is not a spare terminal — do not expect a usable desktop there.

---
> Account: yours · Region: DE/EUR · Date range: 12 Nov 2025 – 24 Jun 2026
> 56 orders total (46 completed/delivering + 4 cancelled + 6 older orders)
> Each item includes product link and technical specifications

---

## 🧠 Brain — NVIDIA Jetson Orin Nano Super

> Source: [NVIDIA official spec sheet](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/) · Not purchased on AliExpress

### Module: Jetson Orin Nano 8GB

| Spec | Value |
|---|---|
| **AI Performance** | 67 INT8 TOPS (Sparse) · 33 TOPS (Dense) · 17 FP16 TFLOPs |
| **GPU** | NVIDIA Ampere architecture · 1024 CUDA cores · 32 Tensor cores · 1020 MHz |
| **CPU** | 6-core Arm Cortex-A78AE v8.2 64-bit · 1.7 GHz · 1.5MB L2 + 4MB L3 |
| **Memory** | 8GB 128-bit LPDDR5 · 102 GB/s bandwidth |
| **Storage** | microSD card slot (UHS-1, SDR104) + external NVMe via M.2 Key M |
| **Video Encode** | 1080p30 (via 1-2 CPU cores) |
| **Video Decode** | 1× 4K60 (H.265) · 2× 4K30 · 5× 1080p60 · 11× 1080p30 |
| **Power** | 7W / 15W / 25W modes (MAXN = 25W) |
| **Software** | JetPack 6.1+ (CUDA, TensorRT, Isaac, Metropolis, Holoscan) |

### Reference Carrier Board (P3766)

| Spec | Value |
|---|---|
| **Camera** | 2× MIPI CSI-2 22-pin connectors (2-lane and 4-lane) |
| **PCIe** | M.2 Key M (×4 PCIe Gen3) + M.2 Key M (×2 PCIe Gen3) + M.2 Key E (×1 PCIe, USB 2.0, UART, I2S, I2C) |
| **USB** | 4× USB 3.2 Gen2 Type-A · 1× USB Type-C (UFP) |
| **Networking** | 1× Gigabit Ethernet |
| **Display** | 1× DisplayPort 1.2 (+MST) |
| **Wireless** | 802.11ac/a/b/g/n 2.4/5GHz · Bluetooth 5.0 |
| **Expansion** | 40-pin header (UART, SPI, I2S, I2C, GPIO) |
| **Other I/O** | 12-pin button header · 4-pin fan header · DC power jack |
| **Dimensions** | 103mm × 90.5mm × 34.77mm (with heatsink) |
| **Power Supply** | 19V DC (45W, included) |
| **Price** | $249 USD |

### Relevance to this inventory

- **Cameras:** OV9281 global shutter cameras and ESP32-CAM connect via USB; MIPI CSI-2 available for direct camera modules
- **Display:** 5.5" OLED/IPS screens connect via DisplayPort or HDMI adapter
- **Servo control:** Waveshare Serial Bus Servo Driver connects via GPIO/UART
- **Motor control:** BTS7960 H-bridge drivers controlled via GPIO PWM
- **Sensors:** HC-SR04, DHT22, LDR sensors connect via GPIO/I2C/1-wire
- **Power:** Waveshare UPS module provides battery backup for the Jetson
- **USB Hub:** YAHBOOM 4-port USB 3.0 hub expands the 4× USB-A ports
- **AI workloads:** Runs LLMs (Llama 3.1 8B @ 19 tok/s), VLMs (Qwen2 VL, VILA), Vision Transformers (CLIP, DINOv2, SAM2) — ideal for robot vision and control

### Storage — Crucial P310 1TB NVMe SSD

> Source: [Amazon.de](https://www.amazon.de/dp/B0DC8VPSHV)

| Spec | Value |
|---|---|
| **Model** | CT1000P310SSD801 |
| **Capacity** | 1 TB |
| **Form factor** | M.2 2280 |
| **Interface** | PCIe 4.0 x4 NVMe 2.0 |
| **Controller** | Phison E27T |
| **NAND** | Micron 3D QLC NAND |
| **Seq. read** | Up to 7,100 MB/s |
| **Seq. write** | Up to 6,000 MB/s |
| **Random read** | 580,000 IOPS |
| **Random write** | 500,000 IOPS |
| **Endurance** | 220 TBW |
| **MTBF** | 1.5M hours |
| **Warranty** | 5 years |
| **Power** | No DRAM (HMB), 40% better perf-per-watt vs prev gen |

> Plugs into the Jetson Orin Nano Super's M.2 Key M slot (×4 PCIe Gen3) for fast OS + model storage

---

## 🧠 Co-processor — Teensy 4.1 (with pins)

> Source: [PJRC Teensy 4.1](https://www.pjrc.com/store/teensy41.html) · [Amazon.de](https://www.amazon.de/-/en/dp/B08CTM3279)

### Specifications

| Spec | Value |
|---|---|
| **Processor** | NXP i.MX RT1062 · ARM Cortex-M7 @ 600 MHz (overclockable to 912 MHz) |
| **FPU** | 32-bit float + 64-bit double precision (hardware) |
| **Architecture** | Dual-issue superscaler (2 instructions/cycle) |
| **Flash Memory** | 7936 KB (8 MB W25Q64JV) |
| **RAM** | 1024 KB (512 KB tightly-coupled ITCM/DTCM + 512 KB DMA-optimized) |
| **EEPROM** | 4284 bytes (emulated) |
| **Cache** | 32 KB instruction + 32 KB data |
| **QSPI Expansion** | 2 locations for PSRAM (8MB) or Flash chips |
| **Digital I/O** | 55 pins (42 breadboard-accessible) · 3.3V logic (NOT 5V tolerant) |
| **PWM Outputs** | 35 pins (22 independent frequency groups) |
| **Analog Inputs** | 18 pins · 10-bit usable (12-bit hardware) · 0–3.3V |
| **Serial (UART)** | 8 ports (all with FIFOs) |
| **SPI** | 3 ports (1 with FIFO) |
| **I2C** | 3 ports (100/400/1000 kbit/s) |
| **CAN Bus** | 3 ports (1 with CAN-FD) |
| **USB Device** | 480 Mbit/s (high-speed) |
| **USB Host** | 480 Mbit/s (with hot-plug power management, 5-pin header) |
| **Ethernet** | 10/100 Mbit (DP83825 PHY, magjack kit required) |
| **SD Card** | Native SDIO (4-bit) microSD socket |
| **Digital Audio** | 2× I2S/TDM + 1× S/PDIF |
| **DMA** | 32 general-purpose channels |
| **RTC** | Date/time (32.768 kHz crystal, coin cell backup on VBAT) |
| **Timers** | 4× IntervalTimer + 4× Quadrature Encoder + FlexPWM + QuadTimer |
| **Crypto** | Hardware acceleration + true random number generator |
| **Form Factor** | 2.4" × 0.7" (61mm × 18mm) |
| **Power** | 5V via USB or VIN · ~100mA @ 600 MHz · 7W–25W modes |
| **Programming** | Arduino IDE + Teensyduino, PlatformIO, CircuitPython, CMake |
| **Variant** | With pins (pre-soldered headers for breadboard) |

### Relevance to this inventory

- **Motor control:** 35 PWM pins drive BTS7960 H-bridges and servos directly. IBT-2 modules need their **logic VCC on 3.3V, not 5V** (74HC244 threshold), and PWM capped at 25 kHz — see Servos & Motor Control
- **Encoders:** 36GP-555 Hall encoders powered at **3.3V** connect directly to the 4 hardware quadrature decoders — no dividers
- **Sensor interface:** 18 analog inputs (0–3.3V) for LDR and other analog sensors; digital pins for HC-SR04/DHT22; I2C/SPI for digital sensors
- **Servo control:** 8 serial ports for TTL bus servos (STS3215) via Waveshare driver board
- **Encoder feedback:** 4 hardware quadrature decoders for the 36GP-555 motors with Hall encoders (2 motors × 2 channels = exact fit)
- **CAN Bus:** 3 CAN ports for automotive-style robot communication
- **Companion to Jetson:** Handles real-time motor/servo control while Jetson runs AI/vision workloads
- **LiDAR:** ❌ **not on the Teensy.** RPLIDAR C1 goes to a Jetson USB port via its CP2102N adapter — it already contains its own MCU, so the Teensy would only be a middleman. `Serial1` is **free**. See Navigation & LiDAR section
- **ROS 2:** runs micro-ROS as `/teensy_node` over **Dual Serial** (`usb=serial2`) — `if02` carries XRCE-DDS, `if00` stays a human console. Agent is a systemd user service on the Jetson. See [`logs/007`](logs/007-2026-08-04-microros-bringup.md)
- **Ultrasonic:** use the **HC-SR04P** (3.3V, direct connect). The classic 5V HC-SR04 needs a resistor divider on ECHO — pins are not 5V tolerant. Wiring tables in Sensors section

---

## 📡 WiFi Antenna — Bingfu WLAN Antenna Set

> Source: [Amazon.de](https://www.amazon.de/dp/B0CMBTFKCH)

### Specifications

| Spec | Value |
|---|---|
| **Brand** | Bingfu |
| **Frequency** | Dual-band WiFi 2.4 / 5 / 5.8 GHz |
| **Gain** | 3 dBi |
| **Polarization** | Linear vertical |
| **Pattern** | Omnidirectional |
| **Impedance** | 50 Ω |
| **VSWR** | < 2.0 |
| **Connector** | RP-SMA plug (antenna) |
| **Cable** | 25 cm IPX U.FL MHF4 → RP-SMA jack (panel mount), 0.81mm coax pigtail |
| **Interface** | M.2 NGFF (for WiFi adapter cards with M.2 slot) |
| **Antenna length** | 10.5 cm |
| **Operating temp** | -20°C to +80°C |
| **Contents** | 2× WiFi antenna, 2× IPEX U.FL MHF4 coax pigtail cable, 2× PCI slot bracket |
| **Note** | MHF4 pigtail fits M.2 NGFF cards only (NOT Mini-PCIe) |

### Relevance to this inventory

- **Jetson Orin Nano Super:** Carrier board has M.2 Key E slot with WiFi/BT module — these antennas connect via the U.FL MHF4 pigtails to the M.2 WiFi card for improved wireless range
- **Robot communication:** Enables reliable WiFi link between the robot and a host PC for remote control, telemetry streaming, and model deployment

---

## 🎥 Vision & Cameras

### OV9281 120fps Global Shutter USB Camera (×2)
- **Store:** GXIVISION USB Camera Factory Store
- **Link:** https://www.aliexpress.com/item/1005008007123713.html
- **Qty:** 2 · **Total:** €75.55 · **Status:** Pending
- **Specs:**
  - Module No.: **S1M03** (per module datasheet)
  - Sensor: OmniVision OV9281 — **1/4" CMOS**, 3.0µm × 3.0µm pixels, CSP bare die
  - Shutter: Global shutter (no rolling distortion)
  - Resolution: 1280×720 (720p)
  - Max transfer: 1280×720 @ **120fps** · 640×400 @ 210fps · 640×360 @ 210fps
  - Output format: **MJPEG only**
  - Interface: **USB 2.0** (UVC)
  - Power: **920 mW max** (~184 mA @ 5V), USB bus powered, 5V ±5%
  - S/N ratio: 36dB · Max dynamic range: 68dB
  - IR filter: 650 ±10nm · Focus: fixed, 1cm–infinity
  - Module size: 38 × 38 × 22mm ±0.3mm
  - Operating temp: −30°C to +70°C (stable image 0°C to +50°C)
  - Lens: No Distortion 3mm
  - Use case: Fast image recognition, robot vision, stereo vision

⚠️ **USB 2.0 bandwidth is the binding constraint, not port count.** On the Jetson **all four Type-A ports share a single USB 2.0 root bus** (`Bus 01`) — moving a USB 2.0 device between ports, or onto the powered hub, changes nothing.

MJPEG-only is what makes two cameras feasible: raw 720p120 mono would be ~110 MB/s *each*, impossible on USB 2.0. Compressed it is ~4.8 MB/s each, ~9.6 MB/s for the pair against ~35 MB/s usable.

But **throughput is not what fails.** UVC devices reserve *isochronous* bandwidth at enumeration from their **declared** endpoint size, not actual use — a camera consuming 38 Mbps often reserves 150–190 Mbps. Two of those against USB 2.0's ~384 Mbps ceiling sits at the edge, and failure appears at plug-in as `Not enough bandwidth for new device state`. Each camera works alone; the second refuses in combination.

**Fix — set this before first plugging them in:**

```bash
echo "options uvcvideo quirks=128" | sudo tee /etc/modprobe.d/uvcvideo.conf
sudo modprobe -r uvcvideo && sudo modprobe uvcvideo quirks=128
cat /sys/module/uvcvideo/parameters/quirks     # expect 128
```

`128` = `0x80` = `UVC_QUIRK_FIX_BANDWIDTH`. It sizes the reservation from `dwMaxPayloadTransferSize` — the value negotiated for the format actually selected. **Without it, lowering resolution or frame rate barely reduces the reservation**, which is why that failure feels irrational. The quirk is what makes every other mitigation work; it comes first, not last.

Trade-off: MJPEG frame size varies with scene complexity, so a smaller alt setting can drop or tear frames under visual load. `nodrop=1` retains incomplete frames for diagnosis.

Also: MJPEG-only means the Jetson CPU-decodes every frame, and JPEG artifacts sit between the global shutter and any precision stereo work.

### Logitech Brio 500 Full HD Webcam
- **Store:** Amazon.de
- **Link:** https://www.amazon.de/dp/B07W5JKKFJ
- **Qty:** 1 · **Status:** Completed
- **Specs:**
  - Resolution: 1080p Full HD (1920×1080)
  - Framerate: 30fps (60fps at 720p)
  - Lens: Auto light correction (RightLight 4)
  - Features: Point mode (digital pan/tilt), Show Mode
  - Microphone: Dual omni-directional with noise cancellation (RightSound)
  - Privacy: Built-in webcam cover
  - Connector: USB-C
  - FOV: 70° / 65° / 55° (adjustable)
  - Color: Graphite
  - Compatible: Microsoft Teams, Google Meet, Zoom, USB-C plug-and-play
  - Use case: High-quality webcam for robot teleoperation / video streaming

---

## 🖥️ Displays

### 5.5" AM-OLED 1920×1080 Touchscreen (RPi) — pending delivery
- **Store:** Wisecoco Global Factory 2nd Store
- **Link:** https://www.aliexpress.com/item/1005004285318699.html
- **Qty:** 1 · **Total:** €35.39 · **Status:** Pending
- **Specs:**
  - Panel: AM-OLED
  - Resolution: 1920×1080 (FHD)
  - Size: 5.5 inch
  - Touch: Multi-touch (capacitive)
  - Refresh rate: 60Hz
  - Interface: HDMI + driver board
  - Compatible: Raspberry Pi (driver board included)
  - Variant: Screen Only (no case)

### 5.5" IPS Display 1920×1080 Touch Panel (RPi) — BROKEN, replaced
- **Store:** Wisecoco Display Store
- **Link:** https://www.aliexpress.com/item/1005003173198690.html
- **Qty:** 1 · **Total:** €78.94 · **Status:** Completed (27 Apr 2026) — **broken, replaced by AM-OLED below**
- **Specs:**
  - Panel: IPS (not OLED)
  - Resolution: 1920×1080 (FHD)
  - Size: 5.5 inch
  - Touch: Touch panel
  - Compatible: Raspberry Pi 4/3B+, camera, PS4, Win10
  - Variant: Whole set (includes driver board + cables)

### ESP32 Dev Board 2.8" LCD Touch Screen
- **Store:** CCSN SAMA Store
- **Link:** https://www.aliexpress.com/item/1005011858576495.html
- **Qty:** 1 · **Total:** €8.64 · **Status:** Completed
- **Specs:**
  - MCU: ESP32 (WiFi + Bluetooth)
  - Display: 2.8" TFT LCD
  - Touch: Resistive touch
  - Interface: SPI
  - Compatible: Arduino IDE
  - Power: 3.3V/5V

### 1.69" LCD IPS Display 240×280 (ST7789V2, SPI)
- **Store:** DIYzone Store
- **Link:** https://www.aliexpress.com/item/1005005752009686.html
- **Qty:** 1 · **Total:** €8.59 · **Status:** Completed
- **Specs:**
  - Controller: ST7789V2
  - Size: 1.69 inch
  - Resolution: 240×280
  - Colors: 262K (18-bit)
  - Interface: SPI (4-wire)
  - Panel: IPS
  - Compatible: Arduino, ESP32, Raspberry Pi 4B/3B+/Zero

### DisplayPort → HDMI Adapter (4K)
- **Store:** LccKaa Choice Store
- **Link:** https://www.aliexpress.com/item/1005009893066622.html
- **Qty:** 1 · **Total:** €0.80 · **Status:** Completed
- **Specs:**
  - Type: DP to HDMI (unidirectional)
  - Max resolution: 4K
  - Audio: Pass-through

### UPERFECT Monitor Stand VESA Mount
- **Store:** Mobile_Monitor Store
- **Link:** https://www.aliexpress.com/item/1005008077039118.html
- **Qty:** 1 · **Total:** €22.69 · **Status:** Completed (12 Nov 2025)
- **Specs:**
  - VESA: 75mm mount
  - Adjustable: Height adjustable
  - Type: Freestanding desk mount
  - Fits: 13.3–18.5 inch screens

---

## 🦾 Servos & Motor Control

### STS3215 12V 30KG TTL Serial Bus Servo (×16)
- **Store:** Feetech Official Store
- **Link:** https://www.aliexpress.com/item/1005008670304643.html
- **Qty:** 3 · **Total:** €299.90 (refunded) · **Status:** Completed
- **Specs:**
  - Model: FEETECH STS3215
  - Torque: 30 kg·cm (at 12V)
  - Voltage: 12V (6-16V range)
  - Communication: TTL serial bus (daisy-chain)
  - Feedback: Position, speed, temperature, load
  - Gear: Metal gears
  - Use case: SO-ARM100 / LeRobot robot arm
  - Variant: 6pcs packaging

### Waveshare Serial Bus Servo Driver Board
- **Store:** Raspberry Pi Store
- **Link:** https://www.aliexpress.com/item/1005008828027133.html
- **Qty:** 1 · **Total:** €18.76 · **Status:** Pending
- **Specs:**
  - Brand: Waveshare
  - Function: Serial bus servo driver/controller
  - Compatible: ST/SC series servos (FEETECH)
  - Integrated: Power supply + control circuitry
  - Interface: For Raspberry Pi GPIO
  - Use case: Driving TTL serial bus servos from RPi

### PCA9685 16-Channel 12-bit PWM Servo Driver (I2C)
- **Store:** Amazon.de (JZK)
- **Link:** https://www.amazon.de/dp/B06XSFFXQY
- **Qty:** 1 · **Status:** Completed
- **Specs:**
  - IC: PCA9685 (Adafruit-compatible)
  - Channels: 16 PWM outputs (12-bit resolution, 4096 steps)
  - Interface: I2C (address 0x40, configurable 0x40–0x7F for chaining)
  - Voltage: 3.3V logic / 5V servo power (V+ pin, separate supply)
  - PWM frequency: 40Hz–1600Hz (adjustable, 50Hz typical for servos)
  - Output: 3.3V PWM signal, drives standard RC servos and LEDs
  - Chaining: Multiple boards via I2C address jumpers (up to 62 boards = 992 servos)
  - Compatible: Arduino, Teensy, Raspberry Pi, Jetson (via I2C/GPIO)
  - Use case: Driving multiple servos from a single I2C bus — offloads PWM generation from the main controller

**Power:** V+ (the large terminal, not the small VCC pins) needs a **5V supply capable of the servo stall current** — ❓ **source undecided, see the 5V rail open question in Power & Battery.** The small VCC pins only run the I2C chip; V+ is what actually drives current through the servos. Logic side (VCC/SDA/SCL) runs at 3.3V from the Teensy.

> ⚠️ This board may not be in the new design at all — if the pan/tilt moves to STS3215 bus servos, the PCA9685 and its 5V rail both disappear.

⚠️ **Known past failure:** a MINI560 was previously wired to this board and produced nothing. Most likely cause is the module's **7V input minimum** — it was fed from a 5V rail, which is below the floor and violates the ≥2V input-to-output headroom rule. Feed it from the 12V pack. Other candidates, in order: ground not shared back to the controller (servos won't move even with good 5V), reversed IN/OUT pads, V+ terminal never wired. Verify with a bare-output 12V bench test before rewiring.

### DC Dual Servo Gimbal Pan/Tilt Bracket + 2× 9G servo
- **Store:** Tangtang Any Shop
- **Link:** https://www.aliexpress.com/item/1005005666356097.html
- **Qty:** 1 · **Total:** €19.38 · **Status:** Pending
- **Specs:**
  - Type: Pan/tilt gimbal bracket
  - Size: 29×29mm
  - Servos: 2× SG90 9G servo included
  - Voltage: 4.8–5V
  - Use case: Camera pan/tilt, FPV head tracker

### 36GP-555 Planetary Gear Motor with Hall Encoder (×2)

> Source: [Kegu Motor 36mm gear motor with encoder](https://kegumotor.com/en/product/36mm-gear-motor-with-encoder.html) · [Precision Microdrives NFP-36GP-555-EN](https://precisionminidrives.com/product/36mm-dc-planetary-gear-motor-with-encoder-model-nfp-36gp-555-en)

- **Store:** ZENG WHCD Manufacturer Store
- **Link:** https://www.aliexpress.com/item/1005010719108956.html
- **Qty:** 2 · **Total:** €75.98 · **Status:** Completed (27 Apr 2026)
- **Specs:**
  - Model: 36GP-555
  - Voltage: 12V (12-24V range)
  - RPM: 160 RPM
  - Gear: Planetary, all-metal
  - Feedback: Hall effect sensor + encoder
  - Bracket: With fixed mounting bracket
  - Use case: Robot drive motors with speed/position feedback

#### Encoder specification

| Item | Value |
|---|---|
| Type | AB two-phase incremental magnetic Hall |
| **Supply voltage** | **3.3V or 5.0V** — output level follows supply |
| Base resolution | 17 PPR (34-pole magnetic ring, 17 pole pairs) |
| Output | Square wave, A/B phase |
| Response frequency | 100 kHz |
| Pull-up | Built in (to encoder VCC) — direct MCU connection, no external parts |
| Connector | XH2.54-6P (2 motor + 4 encoder) |

#### Encoder wiring to Teensy 4.1

**Power the encoder at 3.3V.** Output level follows supply, so 3.3V VCC gives 3.3V square waves straight into Teensy pins — no dividers, no level shifter. The internal pull-up goes to encoder VCC, so it pulls to 3.3V as well.

| Encoder wire | Teensy 4.1 | Note |
|---|---|---|
| VCC | **3.3V** | 5V would make the outputs 5V — damages Teensy pins |
| GND | GND | common ground |
| Phase A | quadrature decoder pin | |
| Phase B | quadrature decoder pin | |

Teensy 4.1 has **4 hardware quadrature decoders** — two motors × two channels fits exactly, zero interrupt load on the CPU. 17 PPR × 4 (quadrature) × gear ratio is far below both the encoder's 100 kHz response and anything the Teensy would notice.

⚠️ **Verify wire colors on the actual motors with a meter before rewiring.** The common 6-wire 36GP-555 scheme is red = motor M1, white = motor M2, **blue = encoder VCC**, black = encoder GND, yellow = phase A, green = phase B. Vendors vary, and the legacy Arduino wiring notes recorded encoder VCC as *red*. Getting this wrong puts the 12V motor rail into the encoder supply.

### Double BTS7960 43A H-Bridge Motor Driver (×2) — IBT-2 module

> Source: [Infineon BTS7960 datasheet rev 1.1](https://www.infineon.com/assets/row/public/documents/10/57/infineon-bts7960-ds-en.pdf) · [Handson Technology IBT-2 module guide](https://www.handsontec.com/dataspecs/module/BTS7960%20Motor%20Driver.pdf) · [Nexperia 74HC244](https://assets.nexperia.com/documents/data-sheet/74HC_HCT244.pdf)

- **Store:** KaiHang Electron Store
- **Link:** https://www.aliexpress.com/item/1005009794997296.html
- **Qty:** 2 · **Total:** €9.09 · **Status:** Completed (27 Apr 2026)
- **Specs:**
  - Driver IC: BTS7960B (×2 per module, PN half-bridge each → full H-bridge)
  - Onboard logic: **74HC244 octal buffer** between header and driver inputs — see logic level note
  - Max current: 43A peak per bridge
  - Motor supply (B+): 6–27V
  - **Max PWM frequency: 25 kHz** (Infineon §4.2 — hard limit)
  - Control input level: 3.3–5V (module marketing claim; see caveat)
  - Duty cycle: 0–100%
  - Protection: overtemperature, overvoltage, undervoltage, overcurrent, short circuit; internal dead-time generation
  - Board: 50 × 50 × 43mm, ~66g
  - Use case: Bidirectional DC motor control (robot drive)

#### Header pinout (8-pin control side)

| Pin | Name | Function |
|---|---|---|
| 1 | RPWM | Forward level or PWM, active high |
| 2 | LPWM | Reverse level or PWM, active high |
| 3 | R_EN | Forward drive enable, active high / low disables |
| 4 | L_EN | Reverse drive enable, active high / low disables |
| 5 | R_IS | Forward-side current alarm / current sense output |
| 6 | L_IS | Reverse-side current alarm / current sense output |
| 7 | VCC | Logic supply — **powers the 74HC244** |
| 8 | GND | Logic ground |

Power side terminals: B+ / B− (6–27VDC supply), M+ / M− (motor output).

#### BTS7960B input thresholds — Infineon §4.4.6

| Parameter | Min | Typ | Max |
|---|---|---|---|
| High level voltage `INH` | — | 1.75V | **2.15V** |
| High level voltage `IN` | — | 1.6V | **2.0V** |
| Low level voltage `INH`/`IN` | 1.1V | 1.4V | — |
| Input hysteresis | — | 350mV (INH) / 200mV (IN) | — |
| Logic input absolute max | −0.3V | — | 5.3V |

The silicon is 3.3V-friendly — datasheet states "The BTS 7960 can be interfaced directly to a microcontroller." **The chip is not the problem. The module's buffer is.**

#### ⚠️ Logic level — the 74HC244 gotcha

The IBT-2 inserts a 74HC244 octal buffer between the header and the driver inputs, powered from **header pin 7 (VCC)**. 74HC thresholds scale with that supply (Nexperia static characteristics):

| Buffer VCC | V_IH min |
|---|---|
| 2.0V | 1.5V |
| 4.5V | 3.15V |
| **5.0V** | **3.5V** (0.7 × VCC) |
| 6.0V | 4.2V |

Teensy 4.1 outputs 3.3V — **below the guaranteed threshold when VCC = 5V.** Real 74HC parts usually switch near VCC/2 so it often appears to work on the bench, then drifts with temperature or board batch. This is the classic ESP32-on-IBT-2 failure.

**Fix: wire header pin 7 (VCC) to Teensy 3.3V, not 5V.** 74HC operates down to 2.0V, so at VCC = 3.3V the threshold becomes 2.31V — Teensy clears it with ~1V margin. The buffer then outputs a 3.3V swing, and the BTS7960B needs only 2.15V to read high. Both datasheets satisfied, no level shifter, no extra parts. A separate/cleaner 5V supply does **not** fix this — any 5V on pin 7 recreates the problem.

**Consequence:** once the buffer runs at 3.3V, nothing on pins 1–4 may exceed 3.3V (74HC absolute max is VCC + 0.5V). `R_EN`/`L_EN` must be strapped to **3.3V**, not a 5V rail — or better, driven from Teensy GPIO so there is a software kill switch.

Buffer current draw is microamps; two modules are nothing against the Teensy 3.3V regulator's ~250mA.

#### ⚠️ `R_IS` / `L_IS` — do not wire to an analog pin unbuffered

Current-sense ratio `kILIS = I_L / I_IS`, typical 8.5 (spec range 3–14 depending on load). With the module's 1kΩ sense resistor, `V_IS = (I_load / 8.5)` volts — so **3.3V is reached at ~28A**, inside this driver's normal range. In a fault the chip switches to a fixed current source `I_IS(lim)` up to **7mA**, which across 1kΩ wants 7V.

Both exceed the Teensy 0–3.3V ADC input. Leave them unconnected, or add a divider.

#### Wiring to Teensy 4.1

| Module pin | Teensy 4.1 | Note |
|---|---|---|
| VCC (7) | **3.3V** | not 5V — this is the whole fix |
| GND (8) | GND | common ground |
| RPWM (1) | any PWM pin | `analogWriteFrequency(pin, 20000)` |
| LPWM (2) | any PWM pin | never drive both high simultaneously |
| R_EN (3) | GPIO or 3.3V | 3.3V only, never 5V |
| L_EN (4) | GPIO or 3.3V | 3.3V only, never 5V |
| R_IS (5) | unconnected | or divider — see above |
| L_IS (6) | unconnected | or divider — see above |
| B+ / B− | 3S LiPo | 11.1V nominal, within 6–27V |
| M+ / M− | motor | |

#### PWM frequency

```cpp
analogWriteFrequency(RPWM_PIN, 20000);  // 20 kHz: above audible, under the 25 kHz limit
analogWriteResolution(12);
```

Teensy 4.1 defaults to 4482 Hz — audible whine, must be set explicitly. **Do not exceed 25 kHz.** The legacy Arduino Nano configuration ran ~31.4 kHz, which is 25% past the Infineon limit — extra switching loss and heat in a part already handling high current. Not an instant failure, which is why it went unnoticed.

---

## 🛰️ Navigation & LiDAR

### RPLIDAR C1 (C1M1) — 360° DTOF Laser Scanner

> Source: [SLAMTEC C1M1-R2 datasheet rev 1.0 (2023-10-13)](https://d229kd5ey79jzj.cloudfront.net/3157/SLAMTEC_rplidar_datasheet_C1_v1.0_en.pdf) · [User manual](https://cdn.robotshop.com/media/R/Rpk/RB-Rpk-35/pdf/rp-lidar-360-tof-lidar-user-manual.pdf) · [youyeetoo C1M1-R2 wiki](https://wiki.youyeetoo.com/en/Lidar/C1M1-R2) · [SDK](https://github.com/Slamtec/rplidar_sdk)

- **Store:** youyeetoo (Amazon.de)
- **Link:** https://www.amazon.de/dp/B0CNXLJJ61
- **Qty:** 1 · **Status:** Completed
- **Specs:**
  - Manufacturer: SLAMTEC
  - Model: C1M1-R2
  - Technology: SL-DTOF (Direct Time of Flight) fusion ranging
  - Range: 0.05–12m (white/70% reflectivity) · 0.05–6m (black/10% reflectivity)
  - Sample rate: 5,000 samples/sec (5KHz)
  - Scanning frequency: 8–12Hz (10Hz typical, 600rpm)
  - Angular resolution: 0.72°
  - Accuracy: ±30mm
  - Resolution: 15mm
  - Scan field: 360° omnidirectional
  - Laser: 905nm infrared, 20W peak, 1.4ns pulse, IEC-60825 Class 1 (eye-safe)
  - Interface: 3.3V TTL UART @ 460800 baud, 8n1
  - Power: 5V DC, 230mA (800mA startup)
  - Connector: XH2.54-5P male socket (4 wires populated)
  - Protection: IP54
  - Anti-ambient light: 40,000 lux
  - Dimensions: 55.6 × 55.6 × 41.3mm · 110g
  - Working temp: -10°C to +40°C · Storage: -20°C to +60°C
  - SDK: Windows, Linux (x86/ARM), macOS, ROS, ROS2 · RoboStudio Framegrabber for test
  - Protocol: compatible with RPLIDAR S series + A series standard sampling protocol
  - Use case: Robot SLAM, mapping, navigation, obstacle avoidance

#### Connector pinout — XH2.54-5P

Datasheet Figure 2-6. Five-position housing, four wires used. **No MOTOCTL pin on C1** (some third-party pages claim one — wrong). Motor is closed-loop internal; speed set by command, and it cannot start/stop independently of the laser scan command.

> ⚠️ **The motor holds its last command — killing the driver does not stop it.**
> There is no MOTOCTL line to de-assert and no hardware timeout. Once told to scan, the C1 keeps spinning until it is told to stop or loses power. A driver that is killed, crashes, or is sent SIGTERM leaves the motor running indefinitely — it does **not** free-run on USB power, but it does keep obeying its last order.
>
> Any tool that starts a scan must send an explicit stop. ROS nodes need **SIGINT** (`rclcpp` shutdown handlers do not run on SIGTERM through `ros2 launch`), and `rplidar.service` also writes the raw stop as a backstop.
>
> **Emergency stop, no ROS needed:**
> ```bash
> printf "\xA5\x25" > /dev/ttyUSB0     # RPLIDAR protocol: A5 25 = STOP
> ```
> See [`logs/009`](logs/009-2026-08-04-lidar-motor-kept-spinning.md).

| Wire | Signal | Type | Min | Typ | Max |
|---|---|---|---|---|---|
| Red | VCC | Power | 4.8V | 5V | 5.2V |
| Yellow | TX (lidar → host) | Output | 0V | — | 3.5V |
| Green | RX (host → lidar) | Input | 0V | — | 3.5V |
| Black | GND | Power | 0V | 0V | 0V |

#### UART electrical — Figure 2-8

| Param | Min | Typ | Max |
|---|---|---|---|
| Baud rate | — | 460800 | — |
| Frame | — | 8 data, 1 stop, no parity (8n1) | — |
| Output high (TX) | 2.9V | 3.3V | 3.5V |
| Output low (TX) | — | — | 0.4V |
| Input high (RX) | 2.4V | 3.3V | 3.5V |
| Input low (RX) | 0V | — | 0.4V |

#### Power supply — Figure 2-7

| Item | Min | Typ | Max | Note |
|---|---|---|---|---|
| Power voltage | 4.8V | 5V | 5.2V | ±4% window; low voltage = inaccurate ranging |
| Ripple | — | — | **150 mV** | excess noise increases lidar radiation |
| Startup current | — | 800 mA | — | cold-start surge |
| Running current | — | 230 mA | 260 mA | 5V, 10Hz scan |

Datasheet note: voltage measured **at the lidar connector** must read above 5V during normal operation — measure there, not at the regulator, so wire drop is included.

**Self-protection (datasheet p.16):** C1 shuts down the laser and stops scanning by itself if scan speed is unstable, scan speed is too slow, or **external power is low**. A brownout therefore presents as a driver/firmware fault, not as a dead device. Host can read status over UART and restart the unit.

#### Connection — Jetson USB (NOT the Teensy)

> **Decided 2026-08-04, verified working.** The C1 goes to a **Jetson USB port via its bundled adapter**. It is not wired to the Teensy. See [`logs/002`](logs/002-2026-08-04-usb-topology-and-peripheral-split.md) for the reasoning and [`logs/004`](logs/004-2026-08-04-rplidar-c1-bringup.md) for the bring-up.

The C1 contains its own microcontroller — it fires the laser, times the return, tracks rotor angle, and hands over **finished measurements**. There is no timing-critical work left for a co-processor to do. Putting the Teensy in between would make it a middleman copying bytes, while:

- adding ~40 KB/s of scan traffic to the same link carrying motor commands, jittering the one path that actually needs determinism
- discarding `rplidar_ros` (already in `~/ros2_ws/src`, with a launch file for this exact model)
- timestamping scans later and less predictably, which directly costs SLAM accuracy

| Item | Value |
|---|---|
| Adapter | Silicon Labs **CP2102N** (`10c4:ea60`), driver `cp210x` |
| Device | `/dev/ttyUSB0` — `root:dialout 660`, `jarvis` already in `dialout`, **no udev rule needed** |
| Stable path | `/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_ec8fc9bc95d5ef11afac704b49d2c684-if00-port0` |
| Power | USB bus power — **no converter, no bulk cap, no ripple constraint** |
| Driver | `ros2 launch rplidar_ros rplidar_c1_launch.py serial_port:=<by-id path>` |

⚠️ **Use the stable by-id path, never `/dev/ttyUSB0`.** The launch file defaults to `/dev/ttyUSB0`, so `serial_port:=` must be passed explicitly. Raw node numbers move on re-enumeration.

**Plug into a Jetson port directly, not the powered hub.** The hub's 12V input sags under motor load, and the C1 **shuts down its laser on low input power** — which presents as a driver fault, not a power fault. Keep the cable short; drop eats the 4.8–5.2V window.

The 800mA cold-start surge fits a USB 3.0 port's 900mA budget. USB 2.0 budgets only 500mA, so avoid unpowered hubs.

<details>
<summary>Superseded: Teensy <code>Serial1</code> wiring (kept for reference — do not build this)</summary>

The original plan wired the C1 to Teensy pins 0/1 at 3.3V TTL, powered from a dedicated MINI560. It required: a 100Ω–1kΩ series resistor on lidar TX (C1 output high is specified to 3.5V against the RT1062's 3.6V ESD clamp — only 100mV margin), 470–1000µF ∥ 0.1µF bulk capacitance for the start surge, a **dedicated** converter because SG90 stall transients exceed the C1's 150mV ripple limit, and `Serial1.addMemoryForRead(buf, 4096)` before `begin(460800)` since the default 64-byte RX buffer cannot hold a ~25 KB/s stream.

All of it is unnecessary now. Recorded only so the reasoning is not re-derived.

</details>

---

## 🔌 Sensors

### HC-SR04 Ultrasonic Distance Sensor (2pcs)

> Source: [Handson Technology HC-SR04 user guide V2.0](https://www.handsontec.com/dataspecs/HC-SR04-Ultrasonic.pdf) · [components101 HC-SR04](https://components101.com/sensors/ultrasonic-sensor-working-pinout-datasheet)

- **Store:** TENSTAR ROBOT Store
- **Link:** https://www.aliexpress.com/item/1005006987195845.html
- **Qty:** 1 set (2pcs) · **Total:** €1.99 · **Status:** Completed
- **Specs:**
  - Range: 2cm–400cm
  - Accuracy: ~3mm
  - Voltage: 5V DC (classic module; unreliable below ~4.5V)
  - Current: <15mA operating, <2mA quiescent
  - Interface: Trigger/Echo (digital), **5V TTL levels**
  - Frequency: 40kHz
  - Effective angle: 15°
  - Variant: 2PCs HC-SR04

⚠️ **ECHO outputs 5V — needs a divider before any Teensy pin.** See wiring below.

### HC-SR04P Ultrasonic Sensor — wide voltage (2pcs)

> Source: [Fred's Cave HC-SR04P](https://www.fredscave.com/sensors/dis-011hc-sr04p.html) · [Cytron: newer vs earlier HC-SR04P](https://www.cytron.io/tutorial/differences-between-newer-and-earlier-versions-of-ultrasonic-sensor-hc-sr04p)

- **Store:** Top-Handicraft Dropshipping Store
- **Link:** https://www.aliexpress.com/item/1005006716282962.html
- **Qty:** 1 set (2pcs) · **Total:** €1.87 · **Status:** Completed
- **Specs:**
  - Range: 2cm–450cm @5V · 2cm–400cm @3.3V
  - Voltage: 2.8–5.5V (wide voltage, 3.3V compatible)
  - Current: 5.3mA
  - Interface: Trigger/Echo · RCWL-9610 controller (also supports I2C/UART/1-Wire via M1/M2 jumpers; unsoldered = classic Trig/Echo mode)
  - Advantage: Works with 3.3V logic (unlike standard HC-SR04) — drop-in replacement footprint

✅ **Preferred part for Teensy 4.1.** Direct connect when powered at 3.3V.

### Ultrasonic — shared timing spec

Handson Technology user guide, Figure 4. Applies to both variants.

| Item | Value |
|---|---|
| Trigger pulse | 10µs high, minimum |
| Sonic burst | 8 cycles @ 40kHz |
| Echo pulse width | 100µs – 18ms |
| Echo when nothing detected | ~38ms |
| Measurement cycle | **>60ms** (prevents trigger bleeding into echo) |
| End of echo → next trigger | ≥10ms |
| Range formula | `µs / 58 = cm` · `µs / 148 = inch` |

Target surface should be ≥0.5m² for a stable reading.

### Ultrasonic — wiring to Teensy 4.1

Teensy 4.1 pins are 3.3V and **not 5V tolerant**. The two variants are handled differently.

#### HC-SR04P — direct, powered at 3.3V

| Sensor pin | Teensy 4.1 | Note |
|---|---|---|
| VCC | 3.3V | **must be 3.3V** |
| TRIG | any digital pin | direct, 3.3V out |
| ECHO | any digital pin | direct, 3.3V out |
| GND | GND | |

**ECHO output level follows VCC.** Powering this module at 5V makes ECHO a 5V output into a non-5V-tolerant pin. The part is 3.3V *compatible*, not 3.3V *protected* — the 3.3V supply is what makes the direct connection safe.

Current draw 5.3mA each; two units ≈ 11mA off the Teensy 3.3V regulator (~250mA available for external loads). Fine.

#### HC-SR04 (classic 5V) — divider required on ECHO

| Sensor pin | Teensy 4.1 | Note |
|---|---|---|
| VCC | 5V — ❓ **source undecided** (see Power & Battery) | not the Teensy 3.3V pin. Avoided entirely by using the HC-SR04**P** at 3.3V |
| TRIG | any digital pin | direct; 3.3V drives it in practice |
| ECHO | any digital pin | **via 1.8kΩ series + 3.3kΩ to GND** = 3.24V |
| GND | common GND | |

- Alternative divider pair: 1kΩ / 2kΩ = 3.33V. No level-shifter module in this inventory, so resistors it is.
- Divider source impedance ~1.2kΩ against a few pF of input capacitance — nanosecond edges, irrelevant against microsecond echo timing.
- **TRIG caveat:** board revisions vary. A CMOS-input clone at 5V VCC wants 0.7×VCC = 3.5V to register a high. Flaky triggering points here — drop module VCC to ~4.5V or level-shift the line up.
- Listing says 5V, but the Handson guide covers a V2.0 board specced 3.3–5V. Revision is not identifiable from the AliExpress page. **Measure ECHO idle-high against GND before wiring.**

#### Firmware notes

- **Avoid `pulseIn()`** — blocks up to 38ms per no-echo reading. Two sensors polled that way cost 76ms of a realtime control loop. Use `attachInterrupt()` on ECHO with `CHANGE`, timestamp via `micros()`, drive triggers from an `IntervalTimer`. All Teensy 4.1 digital pins support interrupts.
- **Cross-talk:** both sensors chirp at 40kHz; overlapping fields mean one hears the other's burst. Fire sequentially, never simultaneously. The 60ms cycle floor allows ~8 alternating readings/sec per sensor.

### AM2302 / DHT22 Temperature & Humidity Sensor
- **Store:** YX Electronic Components
- **Link:** https://www.aliexpress.com/item/32759901711.html
- **Qty:** 1 · **Total:** €1.24 · **Status:** Completed
- **Specs:**
  - Temperature: -40°C to +80°C (±0.5°C)
  - Humidity: 0–100% RH (±2%)
  - Voltage: 3.3–6V DC
  - Interface: Single-wire digital
  - Sampling: 0.5Hz (every 2s)

### Voltage Sensor Module Max 25V (5pcs)
- **Store:** DollaTek (Amazon.de)
- **Link:** https://www.amazon.de/dp/B07DJ5TGL8
- **Qty:** 5 · **Status:** Completed
- **Specs:**
  - Type: Voltage detector / divider module
  - Range: 0–25V DC
  - Interface: Analog output (voltage divider, factor ~5)
  - Pins: 3-terminal (VCC, GND, analog out)
  - Compatible: Arduino, Teensy, ESP32 (analog ADC pin)
  - Use case: Battery voltage monitoring, power supply sensing

---

## 🔋 Power & Battery

### Power Rail Architecture

Design rule: **the 5V and 12V rails carry power only — never a signal that touches the Teensy.** Everything on the Teensy side lands at 3.3V (IBT-2 buffer VCC, encoders, HC-SR04P, lidar UART), so no level shifters are needed anywhere in the robot.

### ⚡ Two separate battery packs — this is the core of the design

**There is no single "12V rail".** Two independent 3S packs with their own BMS, chosen to match their loads:

| Pack | Cells | Capacity | **Max current** | Feeds |
|---|---|---|---|---|
| **Power pack** | 3S × **INR21700-40T** | 4000 mAh · 43 Wh | **35 A** (high drain) | drive motors, STS3215 arm servos |
| **Electronics pack** | 3S × **INR21700-50E** | 5000 mAh · 54 Wh | **10 A** (high capacity) | Jetson, Teensy, sensors |

Each has its own **3S 40A BMS** and holder. One spare cell of each type.

**Why this matters more than any converter choice:** a stalled arm tripping the 40 A BMS **cannot** brown out the Jetson. A brownout mid-manipulation — losing SLAM, losing the ROS graph, losing control of the arm that is already jammed — is the worst failure this robot can have, and the split makes it impossible.

The pairing is also right way round: high-drain cells where the current is, high-capacity cells where runtime matters.

> ⚠️ The power pack is the **smaller** one — 43 Wh against 54 Wh. Both arms at rated torque is ~160 W, so **~16 minutes flat out.** Real duty cycles are far lower, but the arms will outrun the Jetson's runtime under heavy use.

### Power Rail Architecture

Design rule: **the power rails carry power only — never a signal that touches the Teensy.** Everything on the Teensy side lands at 3.3V (IBT-2 buffer VCC, encoders, HC-SR04P), so no level shifters are needed anywhere in the robot.

| Rail | Source | Loads | Notes |
|---|---|---|---|
| **12V power pack (3S 40T)** | battery | drive motors via IBT-2 B+, **STS3215 arm servos**, COB LED strip if 12V (via LR7843 MOSFET) | 35 A available — **fuse every branch**, see below |
| **12V electronics pack (3S 50E)** | battery | Jetson, Teensy VIN, anything logic | 10 A available, ~2.8 A drawn |
| **Teensy 3.3V regulator** | onboard | IBT-2 header pin 7 (74HC244 VCC), motor encoders, HC-SR04P | logic reference for everything; ~250 mA available, actual draw a few mA |
| **Jetson USB 5V** | Jetson | RPLIDAR C1, Brio 500 camera | no converter involved — see Navigation & LiDAR |
| **Charger** | **XL4015 #1** | 19V input → 12.6V CC/CV to pack | ⚠️ requires the CC/CV variant — **open item 1** |
| **5V servo rail** | **LM2596S** from 12.6V | SG90 neck pan/tilt servos | ✅ Live. 3A. Adjustable — see the 6V note below |
| **5V lighting rail** | **MINI560** from 12.6V | COB LED strip via D4184 MOSFET | ✅ Live, added 2026-08-26. Dedicated, see below |

#### ✅ Resolved 2026-08-26: two separate 5V rails

Answered by the LED strip bring-up — see [`logs/012`](logs/012-2026-08-26-led-strip-ambient-brightness.md).

| Rail | Converter | Feeds | Why separate |
|---|---|---|---|
| **5V servo** | LM2596S from 12.6V, 3A | SG90 neck servos | |
| **5V lighting** | MINI560 from 12.6V, 5A | COB LED strip via D4184 | The strip sagged the shared rail ~200 mV at full brightness and made the servos strain |

**They were briefly on one rail and it did not work.** With the strip on the LM2596S alongside the servos, driving it to full brightness dropped the pack from 11.13 V to 10.94 V and the neck servos audibly strained. Splitting them fixed it. This is the same "5V dirty rail" grouping the original architecture warned about.

⚠️ **Feed the MINI560 from 12.6V, never from the 5V rail.** Input floor is 7V with a ≥2V headroom rule; 5V in produces nothing. That is the most likely cause of the earlier dead-MINI560 incident recorded in Servos & Motor Control.

Historical, both struck:
- ~~5V quiet (MINI560 #1)~~ — deleted 2026-08-04, lidar moved to Jetson USB
- ~~5V dirty (MINI560 #2)~~ — was SG90 servos, PCA9685 V+, classic HC-SR04, COB LED strip

Still not on any 5V rail: **PCA9685** (not currently used — servos drive from Teensy pins 2/3 directly), **classic HC-SR04** (open item 5 — the HC-SR04P runs at 3.3V).

#### 🔄 Planned: servo rail to 6V

To get more torque out of the SG90s. **Not yet done** — three checks must pass first:

1. **Nothing else on that rail.** Anything rated 5V absolute is damaged at 6V.
2. ⚠️ **Teensy `VIN` must not be fed from it. Teensy 4.1 VIN maximum is 5.5V** — 6V destroys the board. The Teensy currently runs from Jetson USB, so VIN should be unwired; confirm physically.
3. **Set the pot with the load disconnected**, meter on the bare output, then reconnect.

⚠️ These specific SG90s are recorded at **4.8–5V** (Servos & Motor Control), not the 4.8–6V of generic datasheets. 6V is at or past their rating: more torque, but more heat and faster wear on plastic gears already carrying a 5.5" screen. One tilt servo has already been lost to stalling.

**Better fix, using parts already owned:** 2 of the **16× STS3215** bus servos. 25× the torque, metal gears, position feedback, and they run straight off the 12V pack — deleting this rail question entirely. The migration notes already call for exactly this.

Spares: **5 × MINI560** (1 now in use), 1 × XL4015.

> The lidar's ripple sensitivity used to drive this whole architecture — a dedicated quiet rail with ≤150 mV ripple existed solely for it. Moving it to Jetson USB removed the constraint, a converter, and a failure mode.

---

### 🔥 Fusing — the biggest safety gap

**A BMS protects the cells. A fuse protects the wiring. They are not substitutes.**

The 40 A BMS will not notice 7 A flowing through a 3 A wire. A short downstream of the BMS — a chafed servo lead on a moving joint, a dropped tool, a pinched wire against the chassis — sits there dumping 35 A into wire never designed for it, while the BMS reads a normal load.

**Rule: a fuse protects the wire, not the load.** Fuse rating ≤ wire ampacity, and just above the branch's real maximum. If those two do not leave a gap, the wire is too thin.

| Branch | Real max | **Fuse** | Min wire |
|---|---|---|---|
| Power pack main | ~24 A | **30 A** | 14 AWG |
| Arm bus — left | 7.2 A rated / 21.6 A stall | **15 A** | 16 AWG |
| Arm bus — right | 7.2 A rated / 21.6 A stall | **15 A** | 16 AWG |
| Drive motors (via IBT-2) | ⚠️ **unknown** | **20 A** provisional | 14 AWG |
| Electronics pack main | ~2.8 A | **5 A** | 18 AWG |

Silicone wire ampacity (conservative, chassis): 14 AWG ≈ 30 A · 16 AWG ≈ 22 A · 18 AWG ≈ 16 A · 20 AWG ≈ 11 A · 22 AWG ≈ 7 A.

**The 15 A arm fuse is deliberately below stall (21.6 A).** A whole-arm stall *should* cut power. It passes rated torque (7.2 A) and normal transients comfortably.

**Type:** automotive **blade fuses, Standard (ATO/ATC) size** — not Mini. Rated 32 V DC, vibration-tolerant, inherently slightly slow so motor inrush does not nuisance-trip, holders come pre-wired. Standard has more contact area than Mini, so it runs cooler at 20–30 A, which is the failure being guarded against. Avoid glass cartridges (fragile) and PPTC (too slow, too resistive at these currents).

**Placement: as close to the battery terminal as physically possible.** Every centimetre of wire *before* the fuse is unprotected, and that is the wire nearest the highest-energy source.

Also fit a **main disconnect** per pack — one action that kills everything. Deans T-plugs work if they are reachable.

---

### 🦾 Arm power — daisy-chain limits

Each STS3215 has two 3-pin connectors and passes **power and data** through its own PCB. Chain 8 and **the first connector carries all 8 servos' current**.

[STS3215 12V](https://www.feetechrc.com/525603.html) per servo: idle 30 mA · no-load 180 mA · **rated torque 900 mA** · **stall 2.7 A**.

| Arm state (8 servos) | Current through first connector |
|---|---|
| Holding position | 0.24 A |
| Moving, unloaded | 1.44 A |
| Light work, shoulder loaded | ~1–2 A |
| All at rated torque | 7.2 A |
| All stalled | 21.6 A |

Stock bus cable is 24–26 AWG with a 3-pin JST, realistically **2–3 A**.

**For light use, straight daisy-chaining is fine** — 1–2 A is inside the connector's rating, which is why the SO-ARM100 community does it without trouble. The risks, in order of likelihood:

1. **Brownout and bus glitches — most likely, and not a fire.** Voltage drop along the chain means far-end servos see less than near-end. A fast multi-joint move sags the rail and distant servos reset or drop off the bus. **Presents as flaky behaviour that looks like a firmware bug.** If servos start dropping out during fast moves, and it gets worse further down the chain, that is voltage drop — not code.
2. **Gradual connector degradation** — warm cycles raise contact resistance, which makes more heat. Shows up months later as an intermittent joint.
3. **Stall — the one that matters, because it is never planned.** Gripper closes on something immovable, arm swings into the table, software commands a joint past its limit. 2.7 A per servo, with 35 A behind it.

#### What to do, in order of value

| Action | Priority |
|---|---|
| **Fuse the arm branch** (15 A) | **Do it** — €2, covers the unplanned case |
| **Firmware torque/current limit** | **Do it** — the STS3215 accepts a cap over the bus and reports per-servo current, voltage and temperature. This *bounds the jam case entirely*, and acts before anything heats. Better protection than the fuse, because a fuse cannot tell a hard lift from a jam |
| **Star-wire the power** | **When you load the arm, or when symptom 1 appears** — not needed for light use |

#### Star wiring, when it becomes necessary

Split each arm into groups of 2–3 servos, inject 12 V into each group, keep the data chain continuous:

```
                    ┌── 18AWG ──▶ [S1]─[S2]─[S3]   shoulder   2.7A
16AWG               │
pack ──[15A fuse]──▶├── 18AWG ──▶ [S4]─[S5]─[S6]   elbow      2.7A
                    │
                 terminal ─ 18AWG ──▶ [S7]─[S8]    wrist      1.8A
                  block
```

To make an injection cable: take a spare STS3215 cable, **cut GND and 12V** and splice both ends to the feed, **leave the signal wire continuous**. Or buy a bus servo hub (Waveshare/Feetech) for the same result with less soldering.

**Group by load, not convenience** — shoulder joints hold the arm against gravity continuously and deserve the shortest, fattest feed.

⚠️ **Power bypasses the Waveshare adapter entirely.** That board is the UART interface; its 9–12.6 V input powers its own logic. Running 7 A of servo current through it is the thing being avoided.

⚠️ **Ground must be common at one star point** — all injection points, the Waveshare adapter, and the pack negative. The bus is single-wire signalling referenced to ground; a ground offset between groups corrupts data and looks like random servo dropouts.

---

### Power budget

| Load | Current @ 12V | Pack |
|---|---|---|
| Both arms holding | 0.48 A | power |
| Both arms moving, unloaded | 2.88 A | power |
| Both arms at rated torque | 14.4 A | power |
| Drive motors, both | ⚠️ **unknown** (est. ~10 A) | power |
| **Power pack worst realistic** | **~24 A of 35 A (69%)** | ✅ |
| Both arms stalled | 43.2 A | ❌ over 40 A BMS — trips, by design |
| Jetson at 25 W (MAXN) | 2.1 A | electronics |
| Lidar + camera + Teensy + screen | ~0.7 A | electronics |
| **Electronics pack total** | **~2.8 A of 10 A (28%)** | ✅ |

**The architecture has margin.** The gaps are fusing, the arm daisy-chain under load, and an unverified charger — not capacity.

⚠️ **The 36GP-555 current specs are missing** from this document (only voltage and RPM are recorded). That is the one hole in the budget, and it sits exactly where the drive base is. Measure stall current on the bench.

#### Grounding — the actual failure mode

Separate supply rails are harmless on their own. Grounding is where a multi-rail robot goes wrong.

- **Common ground is mandatory.** A 3.3V signal is only 3.3V relative to a shared reference. Separate supplies with separate grounds leave every logic level undefined.
- **Star ground, not daisy chain.** Servo stall current returning through a thin shared wire drops voltage across it. If the Teensy's ground sits downstream of that drop, its 0V reference lifts by hundreds of mV under load and every logic threshold moves with it. Symptom: everything works until the servos move.
- **Never route servo or LED return current through the Teensy GND pin.** Each buck's negative goes directly to the battery negative / star point; the Teensy gets its own spur to that same point.
- **VUSB / VIN:** if Teensy VIN is ever fed from a buck while USB is also connected, cut the VUSB↔VIN pad on the board underside first. Not needed if the Teensy stays USB-powered.

#### Charging

19V input → 12.6V CC/CV via **XL4015 #1**, into the 3S pack.

| Setting | Value | Why |
|---|---|---|
| CV | **12.60V** exactly | 4.20V/cell for 3S Li-ion |
| CC | ~2A | 50E max charge 4.75A, 40T max 4A — 2A is gentler, pack lasts longer |

Set both with a meter and **no pack connected**, then connect. Add a **Schottky in series** between buck output and pack — the XL4015 has no reverse-current blocking, so a connected pack leaks backward when the 19V source is off. Set the CV point measured at the pack terminals. Do not use the 10A10 rectifiers for this; a ~1V silicon drop that varies with current wrecks CV accuracy. Simpler alternative: a disconnect plug in the charge path.

⚠️ **The 3S BMS is a safety net, not a charge controller.** It cuts off when a cell exceeds its limit; it does not regulate the charge profile, and passive balancing is slow. Verify the 12.60V setting before the first connection and don't leave early charge cycles unattended — confirm pack voltage plateaus at 12.6V and current tapers.

**This plan requires the CC/CV variant of the XL4015** (two pots + red/blue/green LEDs). If yours has a single pot it is CV-only with no current limit — do not charge lithium with it; use a purpose-built 3S balance charger instead.

---

### Samsung INR21700-50E — 5000mAh 10A Li-ion (×4)
- **Source:** 18650 Battery Store (not AliExpress/Amazon)
- **Qty:** 4 · **Price:** €20.13 · **Status:** Completed (30 Apr 2026)
- **Specs:**
  - Model: Samsung INR21700-50E
  - Chemistry: Li-ion (NCA)
  - Nominal voltage: 3.6V (4.2V charged)
  - Capacity: 5000mAh (18Wh)
  - Max continuous discharge: 10A
  - Max charge: 4.75A
  - Size: 21700 (21mm × 70mm)
  - Use case: High-capacity power bank / battery pack for robot (long runtime)

### Samsung INR21700-40T — 4000mAh 35A Li-ion (×4)
- **Source:** 18650 Battery Store (not AliExpress/Amazon)
- **Qty:** 4 · **Price:** €16.77 · **Status:** Completed (30 Apr 2026)
- **Specs:**
  - Model: Samsung INR21700-40T
  - Chemistry: Li-ion (NCA)
  - Nominal voltage: 3.6V (4.2V charged)
  - Capacity: 4000mAh (14.4Wh)
  - Max continuous discharge: 35A (high drain)
  - Max charge: 4A
  - Size: 21700 (21mm × 70mm)
  - Use case: High-current motor power (BTS7960 drivers, 36GP-555 motors)

> **Combined pack:** 8× 21700 cells — 4× 50E for capacity (electronics/Jetson), 4× 40T for high drain (motors/servos)
> **Order total:** €43.92 (incl. 19% VAT) · PayPal · DHL shipping
> Pairs with: 3S 40A BMS holder (Heltec, pending) + 1S holders (Shop1104891086)

---
### 12V 21700 Battery Holder + 3S 40A BMS (×2) — pending delivery
- **Store:** Heltec IOT Store
- **Link:** https://www.aliexpress.com/item/1005005254270294.html
- **Qty:** 2 · **Total:** €29.18 · **Status:** Pending
- **Specs:**
  - Cell: 21700 (3S1P configuration)
  - BMS: 40A continuous
  - Balance: Yes (balance charging)
  - Output: ~12V nominal (3× 3.7V)
  - Use case: Robot power pack, DIY e-bike, power wall
  - Variant: 3S1P BMS 40A (short)

### Waveshare UPS Module (C) for Jetson Orin Nano Super
- **Store:** Development Board Store
- **Link:** https://www.aliexpress.com/item/1005011566821736.html
- **Qty:** 1 · **Total:** €32.19 · **Status:** Completed (27 Apr 2026)
- **Specs:**
  - Brand: Waveshare
  - Type: Uninterruptible Power Supply (UPS)
  - Compatible: Jetson Orin Nano Super (the robot's brain)
  - Battery: 21700 Li-ion (NOT included)
  - Function: Battery backup / power management

### Heltecbms 18650/21700 1S Battery Holder (×4)
- **Store:** Shop1104891086 Store
- **Link:** https://www.aliexpress.com/item/1005012150486431.html
- **Qty:** 4 · **Total:** €5.56 · **Status:** Completed
- **Specs:**
  - Cell: 21700 (1S configuration)
  - BMS: Standard (3-35A available)
  - Variant: 1S 21700 Standard

### MINI560 DC-DC Step-Down Module — 5V fixed (6pcs)

> Source: [JW5069A / Mini560 teardown — Hackaday](https://hackaday.com/2024/05/26/hunting-for-part-numbers-analyzing-the-buck-converter-on-mini-560-modules/) · [MINI560 5V module listing specs](https://ifuturetech.org/product/mini560-dc-5v-5a-step-down-stabilized-module/)

- **Store:** LAOMAO
- **Qty:** 6 · **Status:** Owned
- **Specs:**
  - Controller: JoulWatt **JW5069A** synchronous buck
  - **Input: 7–20V** — and input must be **≥2V above output**
  - Output: **5V fixed** (no adjustment pot)
  - Current: 3–4A continuous, 4–5A peak
  - Switching frequency: **500 kHz**
  - Rectification: **synchronous**
  - Efficiency: up to ~99% (marketing peak; expect low 90s at 12V→5V)
  - Protection: overcurrent, overtemperature, short circuit
  - Size: 29 × 18 × 5.4mm
  - Operating temp: -40°C to +85°C

**Best 5V source in this inventory.** Fixed output means there is no pot to misadjust or drift — nothing can accidentally put 32V on the load. 500 kHz synchronous gives markedly better transient response and lower ripple than the 180 kHz non-synchronous XL4015, which is what the RPLIDAR C1's ripple limit cares about.

⚠️ **The 7V input minimum is the trap.** Feeding this from a 5V rail produces no usable output — 5V in is both below the 7V floor and violates the ≥2V headroom rule. Feed it from the 12V battery. No published ripple figure exists for this module; measure if the lidar misbehaves.

### XL4015 5A DC-DC Step-Down Module (2pcs, with heatsink)

> Source: [XLSEMI XL4015 datasheet](https://datasheet4u.com/datasheet/Xlsemi/XL4015-786208) · [Handson Technology XL4015 module doc](https://www.handsontec.com/dataspecs/module/XL4015-5A-PS.pdf)

- **Qty:** 2 · **Status:** Owned
- **Specs:**
  - IC: XLSEMI XL4015, 180 kHz fixed-frequency PWM buck
  - **Input: 8–36V** (listings claim 4–38V — wrong, ignore)
  - Output: 1.25–32V adjustable via pot
  - Current: 5A rated (die); heatsink included
  - Output ripple: 50mV max (20MHz bandwidth)
  - Voltage regulation ±2.5% · Load regulation ±0.5%
  - Rectification: **non-synchronous** (Schottky catch diode)
  - Efficiency: 95–96% peak; expect ~87–90% at 12V→5V
  - Minimum dropout: 0.3V

⚠️ **Set the output voltage with a meter before connecting any load.** The pot is multi-turn and the module powers up at whatever it was last left at — **which can be 32V**.

**Variant check:** two pots + red/blue/green LEDs = CC/CV version (usable as a charger). One pot = CV only — **do not charge lithium with it**, there is no current limit.

### MT3608 DC-DC Step-Up Boost Module (5pcs)
- **Store:** JYJD Module Store
- **Link:** https://www.aliexpress.com/item/1005010758770661.html
- **Qty:** 5 · **Total:** €2.69 · **Status:** Completed
- **Specs:**
  - IC: MT3608
  - Input: 2–24V
  - Output: 5–28V (adjustable)
  - Max current: 2A
  - Efficiency: ~93%
  - Size: 17×11mm

### DC-DC Step-Up Battery Charger Module (10pcs)
- **Store:** Large Digital Life Store
- **Link:** https://www.aliexpress.com/item/1005007816583593.html
- **Qty:** 10 · **Total:** €6.49 · **Status:** Completed
- **Specs:**
  - Input: 4.3–27V (adjustable)
  - Function: Step-up + battery charging
  - Battery: Li-Ion/Li-Po charger
  - Variant: 10PCS

### Isolated MOSFET Module (LR7843) — ❌ DOES NOT SWITCH, superseded
- **Store:** YX Electronic Components Store
- **Link:** https://www.aliexpress.com/item/1005007204205450.html
- **Qty:** 1 · **Total:** €1.02 · **Status:** ❌ **Failed in service 2026-08-23**

⚠️ **This module never switched its gate.** Power path was fine — shorting `LOAD` to `−`
lit the load at full — but no drive turned the FET on: not 3.3V from a Teensy pin
(either wire orientation), and not 5V jumpered straight to the header. Connecting it
also dragged the driving pin to 0V. Replaced by the D4184 module below, which worked on
the first bench test. Full debug trail in [`logs/012`](logs/012-2026-08-26-led-strip-ambient-brightness.md).
- **Specs:**
  - MOSFET: LR7843 (also covers FR120N, AOD4184, D4184)
  - Voltage: 100V/30V (depends on variant)
  - Current: up to 161A peak
  - Function: High-power switch, relay replacement
  - Isolated: Opto-isolated gate drive

### D4184 Dual MOSFET Trigger Switch Module (6pcs) — ✅ in service

- **Store:** Amazon.de (AOICRIE)
- **Qty:** 6 · **Total:** €6.99 · **Status:** Owned, 1 in service 2026-08-26
- **Specs:**
  - MOSFET: **AOD4184 ×2 in parallel** — genuine logic level
  - **Trigger: DC 3.3V–20V** — stated as a spec, works directly from a Teensy pin
  - Load supply: DC 5–36V · 15A continuous, 400W · 30A peak with cooling
  - PWM: **0–20 kHz**
  - Terminals: `VIN+` `VIN-` (supply in), `OUT+` `OUT-` (load), header `PWM` / `GND`
- **In service:** COB LED strip, driven from Teensy pin 4 at 18 kHz

Low-side switch, but the four-terminal layout hides that — `VIN+` passes through to
`OUT+` internally and the FETs chop `OUT-` against `VIN-`, so the load just goes across
`OUT+`/`OUT-` in its natural polarity. Much harder to miswire than a `+`/`LOAD`/`−` board.

⚠️ **Do not buy the red "MOS Module" (HW-517) instead — it is IRF520-based.** Its
listings claim 3.3V compatibility, but IRF520 Vgs(th) runs to 4V and Rds(on) is
specified at a 10V gate, so a 3.3V pin leaves it in the linear region: dim output, hot
FET, or nothing. Check the TO-220 marking in the listing photos, not the bullet points.
Logic-level parts that do work: **AOD4184/D4184**, **IRLZ44N**, **IRLB8721**.

### Rectifier Diode 10A10 (50pcs)
- **Store:** DeceKey Electronics Store
- **Link:** https://www.aliexpress.com/item/1005012341427949.html
- **Qty:** 50 · **Total:** €1.80 · **Status:** Completed
- **Specs:**
  - Type: 10A10 rectifier diode
  - Current: 10A
  - Voltage: 1000V reverse
  - Package: R-6 (axial)
  - ⚠️ **Not suitable for charge path** — silicon drop ~0.7-1.0V varies with current, wrecks CV accuracy. Use for AC rectification only.

### Schottky Diode 30SQ050 (20pcs) — for charge path reverse-current protection
- **Store:** Amazon.de (DYOUen) · **ASIN:** B0BYVGWTHD
- **Link:** https://www.amazon.de/dp/B0BYVGWTHD
- **Qty:** 20 · **Price:** €5.99 · **Status:** Ordered 2026-08-19
- **Specs:**
  - Type: 30SQ050 Schottky diode
  - Current: 30A (12× headroom over 2.37A charge current)
  - Voltage: 50V reverse
  - Forward drop: ~0.3-0.4V (Schottky — stable across charge cycle)
  - Package: Axial, 6.2 cm length
- **Use case:** Reverse-current protection between XL4015 output and 3S pack. Prevents battery draining backward through the XL4015 when the 19V source is off. Oriented: anode → converter, cathode (band/`-` side) → pack. Set CV to 12.60V measured at pack terminals (after diode).

---

## 🔗 Cables, Connectors & Hubs

### USB Hub 3.0 4-Port Splitter (9-24V) — pending delivery
- **Store:** YAHBOOM Official Store
- **Link:** https://www.aliexpress.com/item/1005004159313542.html
- **Qty:** 1 · **Total:** €31.16 · **Status:** Pending
- **Specs:**
  - Ports: 4× USB 3.0
  - Power: Micro USB charge, 9–24V input
  - Compatible: Raspberry Pi 5/4B, Jetson Orin Nano, ROS robotic equipment
  - Data: USB 3.0 (5Gbps)

### 240W 40Gbps USB-C to USB-C Cable (90°) — pending delivery
- **Store:** Speeding and Running Digital Store
- **Link:** https://www.aliexpress.com/item/1005009408639864.html
- **Qty:** 1 · **Total:** €11.12 · **Status:** Pending
- **Specs:**
  - Power: 240W (PD 3.1)
  - Data: 40Gbps (USB 4 / Thunderbolt 4)
  - Connector: USB-C to USB-C, 90° angle
  - Cable: Flat, short length

### FPV USB 3.1 Type-C 90° to USB-A FPC Ribbon Cable (30cm)
- **Store:** ADT-LINK Store
- **Link:** https://www.aliexpress.com/item/1005003538137122.html
- **Qty:** 1 · **Total:** €10.46 · **Status:** Completed (27 Apr 2026)
- **Specs:**
  - Type: FPC ribbon flat cable
  - USB: 3.1 Gen2 (10Gbps)
  - Connectors: Type-C 90° → USB-A male
  - Length: 30cm
  - Pins: 13-pin

### FPV HDMI Cable 90° FPC Ribbon (30cm)
- **Store:** wdmly Digital Store
- **Link:** https://www.aliexpress.com/item/1005001417805853.html
- **Qty:** 1 · **Total:** €7.39 · **Status:** Completed (27 Apr 2026)
- **Specs:**
  - Type: Micro/Mini HDMI 90° FPC ribbon
  - Pitch: 20-pin
  - Length: 30cm
  - Use case: FPV / compact HDMI routing

### Soft Flat Cord 10W USB2.0 Charging / Data (30cm)
- **Store:** Shop911048111 Store
- **Link:** https://www.aliexpress.com/item/1005007470552376.html
- **Qty:** 1 · **Total:** €6.16 · **Status:** Completed
- **Specs:**
  - Data: USB 2.0 (480Mbps)
  - Power: 10W charging
  - Connector: Straight head
  - Length: 30cm

### DC Power Extension Cable 5.5×2.5mm (1m, 22AWG)
- **Store:** UpperFu Store
- **Link:** https://www.aliexpress.com/item/1005008376561107.html
- **Qty:** 2 · **Total:** €3.21 · **Status:** Completed
- **Specs:**
  - Connector: 5.5×2.5mm DC barrel jack
  - Type: Male right angle → female
  - Wire: 22AWG
  - Length: 1m

### DC-022B Power Jack Socket (10pcs, 5.5×2.5mm)
- **Store:** TLZWLA Official Store
- **Link:** https://www.aliexpress.com/item/4000555711683.html
- **Qty:** 10 · **Total:** €1.79 · **Status:** Completed
- **Specs:**
  - Type: DC-022B panel mount
  - Rating: 3A, 12V
  - Size: 5.5×2.5mm (also fits 5.5×2.1mm)

### Spring Loaded Pogo Pin 5.5mm 5A (2pcs)
- **Store:** RTLECS Technology Store
- **Link:** https://www.aliexpress.com/item/1005009476766238.html
- **Qty:** 2 · **Total:** €2.99 · **Status:** Completed
- **Specs:**
  - Type: Spring-loaded pogo pin (test probe)
  - Diameter: 5.5mm
  - Current rating: 5A
  - Model: GF55-17770-3533
  - Plating: Gold plated

### Servo Extension Cable 150-500mm Futaba JR (10pcs)
- **Store:** YUGUO baby Store
- **Link:** https://www.aliexpress.com/item/32902360371.html
- **Qty:** 10 · **Total:** €11.67 · **Status:** Completed
- **Specs:**
  - Type: Servo extension cable
  - Connector: Futaba JR (male to female)
  - Length: 150/200/300/500mm
  - Wire: 30cm

### Dupont Jumper Wire F-F 20cm (100pcs)
- **Store:** YouKeyi Store
- **Link:** https://www.aliexpress.com/item/1005006148662373.html
- **Qty:** 100 · **Total:** €3.55 · **Status:** Completed (27 Apr 2026)
- **Specs:**
  - Type: Dupont jumper wire
  - Gender: Female-to-Female
  - Length: 20cm
  - Pitch: 2.54mm
  - Use case: Breadboard / Arduino connections

### T-Plug Harness Parallel Battery Y-Splitter (6pcs)
- **Store:** Shop1105165525 Store
- **Link:** https://www.aliexpress.com/item/1005010158976720.html
- **Qty:** 6 · **Total:** €12.39 · **Status:** Completed (29 Apr 2026)
- **Specs:**
  - Type: T-plug (Deans) parallel connector
  - Configuration: 1 Male to 2 Female
  - Wire: Silicone
  - Use case: RC battery parallel connection

### Deans Ultra Pigtail Cable T-Plug (4pcs)
- **Store:** Shop1105163493 Store
- **Link:** https://www.aliexpress.com/item/1005010302742052.html
- **Qty:** 4 · **Total:** €3.49 · **Status:** Completed (29 Apr 2026)
- **Specs:**
  - Type: T-plug (Deans) pigtail
  - Gender: Male
  - Wire: 14AWG silicone
  - Length: 10cm

---

## 💡 Lighting

### COB LED Strip (magnetic mount)
- **Store:** AliExpress
- **Link:** https://de.aliexpress.com/item/1005009182017881.html
- **Qty:** 1 · **Total:** €8.99 · **Status:** Completed
- **Specs:**
  - Type: COB LED strip light
  - Mounting: Magnetic attachment
  - Colors available: White / Black / Yellow
  - Size: 2.2mm
  - **Voltage: 5V** — measured 2026-08-26, was open item 2
  - Use case: Robot illumination / lighting
- **In service 2026-08-26:** dedicated MINI560 5V rail → D4184 MOSFET → Teensy pin 4 PWM
  at 18 kHz, brightness following the A1 photoresistor. Wiring in `PINOUT.md`,
  bring-up in [`logs/012`](logs/012-2026-08-26-led-strip-ambient-brightness.md)

⚠️ **No inline fuse fitted yet.** This branch is currently unprotected — see Fusing.

### Keyestudio Photoresistor Module — ✅ in service

- **Qty:** 1 · **Status:** In service 2026-08-26
- **Specs:**
  - Photoresistor with the 10k half of the divider **onboard** — no external resistor
  - Pins: `S` (analog out) · `V` (supply) · `G` (ground)
- **Wiring:** `G` → Teensy GND · `V` → **Teensy 3.3V** · `S` → Teensy A1 (pin 15)

⚠️ **Power from 3.3V, never 5V.** `S` is a divider off its own supply, so a 5V module
puts 5V on a 3.3V ADC pin.

Divider polarity varies by batch. Firmware has an `LDR_BRIGHT_IS_HIGH` constant and
`CAL dark` / `CAL bright` console commands to handle it — see `PINOUT.md`.

---

## 🔊 Audio

### NBFINE USB PC Speaker (mini soundbar, clip-on)
- **Store:** Amazon.de (NBFINE)
- **Link:** https://www.amazon.de/dp/B0CPJ1WHCK
- **Qty:** 1 · **Status:** Completed
- **Specs:**
  - Type: Mini soundbar / portable desktop speaker
  - Mounting: Clip-on design (attaches to monitor)
  - Connection: USB (plug and play, no drivers)
  - Includes: USB-A to USB-C adapter
  - Power: USB-powered
  - Use case: Audio output for the robot (alerts, TTS, sound feedback)
- **In service 2026-08-29.** ALSA **card 3**, `USB2.0 Device` at `usb-3610000.usb-2.1.3`.
  Stereo out 48 kHz S16_LE, **plus a mono capture endpoint** — it has a mic of its own.
  Set as the PulseAudio default sink.

⚠️ **The ALSA hardware mixer ships at 15%** (`PCM` = 39/255), which reads as a broken or
faint speaker. PulseAudio's level rides on top of it, so `amixer -c 3 sset PCM <n>%` is
the control that matters — not `pactl set-sink-volume`.

> The sink defaults to the **iec958** (S/PDIF) profile. If PulseAudio playback is silent
> while direct ALSA works, switch the card to `analog-stereo`.

### 🎙️ Wake word — "Gerdoo, baba" (گردو بابا)

Offline Persian wake-word trigger. Full write-up in
[`logs/013`](logs/013-2026-08-29-audio-and-persian-wake-word.md).

| | |
|---|---|
| **Engine** | Vosk, `vosk-model-small-fa-0.42` (97 MB, `~/models/`), CPU, fully offline |
| **Mic** | **Brio 500** — chosen over the speaker's own mic so the robot cannot hear itself |
| **Method** | Decoder grammar with filler competitors, final results only, both words required |
| **Gain** | **3.0×** in software — measured by replay, not guessed |
| **Service** | `wake-word.service`, systemd `--user`, enabled at boot |
| **Measured** | 18/18 detections on the bench. ⚠️ **False positives in real use** — see the correction in log 013 |
| **Range** | ~4 m. Beyond that needs a better mic, not more tuning |

⚠️ **The Brio's capture gain does not survive a reboot**, and the 4 m range depends on it
being at the top of its range (54 dB / 72). The unit re-applies it in `ExecStartPre`.

⚠️ **PortAudio device indices move between reboots and replugs** — the same trap as
`/dev/ttyACM*`. Select the mic by name (`--device-name Brio`), never by index.

⚠️ **`paplay` accepts an mp3 path and silently plays nothing.** That is indistinguishable
from the detector not firing. Use `mpg123` for compressed audio.

### 🔊 Audio routing — read before touching anything that captures or plays

The Brio (capture) and the USB speaker (playback) are **two separate USB devices with
independent clocks**, and that single fact drives everything below. Full write-up in
[`logs/014`](logs/014-2026-09-01-livekit-voice-agent.md).

`wake-word/audio-setup.sh` puts it all back into a known state and runs on every
wake-word service start. Run it by hand whenever audio misbehaves — it prints what it
found.

| Trap | What it looks like |
|---|---|
| **Two processes, one microphone.** `wake_word.py` opens the Brio through raw ALSA and holds `/dev/snd/pcmC2D0c` | Firefox's `getUserMedia` succeeds and captures **silence**. Everything looks connected. The detector now releases the device during a call |
| **`module-stream-restore` overrides the default device per application** | Setting the default source/sink does not move Firefox. It stays on whatever it used last, so the echo canceller is bypassed. It is unloaded |
| **Clock drift between the two devices** | Echo cancellation works for ~30 s then collapses and the robot transcribes its own voice. Fixed with `adjust_time=1 adjust_threshold=1` — resync every second instead of every ten. `adjust_threshold` must be an **integer** or the module fails to load |
| **Replugging the USB hub** | Mixer levels reset (speaker to 15%) and the default source moves to the **speaker's own mic**. The robot goes deaf while looking fine |
| **Card indices move on replug** | Resolve by name (`B500`, `Device`), never `-c 2`. Third time this project has been bitten by addressing USB hardware by number |

⚠️ **Echo cancellation is `module-echo-cancel` in PulseAudio, not the browser.** Browser
AEC cannot work across two devices with no shared clock. Both directions must route
through `gerdoo_aec_source` / `gerdoo_aec_sink` — the canceller can only subtract what it
knows was played.

⚠️ **The speaker has its own microphone.** It is in the same clock domain as the speaker,
so AEC would be trivial — but it is a poor microphone and was rejected. The Brio stays.

---

## 🏎️ RC Car / Robot Wheels & Parts

### 1/10 RC Drift Car Tires + Alloy Wheels (black)
- **Store:** RS RC Store
- **Link:** https://www.aliexpress.com/item/1005009551827316.html
- **Qty:** 1 set · **Total:** €17.78 · **Status:** Completed
- **Specs:**
  - Scale: 1/10
  - Type: On-road drift tires
  - Wheels: Alloy hubs
  - Color: Black
  - Compatible: HSP 94122/94123, Tamiya TT02, HPI, Kyosho Sakura CS/D4

### 12mm Wheel Hex Coupling Brass Adapter (4pcs)
- **Store:** Professional RC Model Store
- **Link:** https://www.aliexpress.com/item/1005008040041427.html
- **Qty:** 4 · **Total:** €2.39 · **Status:** Completed
- **Specs:**
  - Size: 12mm hex
  - Material: Brass
  - Style: Short, 8mm
  - Use case: RC wheel adapter / tire connector

### 65mm Robot Wheel Tires (×2)
- **Store:** AEAK Store
- **Link:** https://www.aliexpress.com/item/1005004918038178.html
- **Qty:** 2 · **Total:** €8.58 · **Status:** Completed (29 Apr 2026)
- **Specs:**
  - Diameter: 65mm
  - Scale: 1/10
  - Type: Smart robot / trolley wheel
  - Feature: High friction tire

### Furniture Caster Wheels 1-inch (4pcs)
- **Store:** NAIERDI Handle Store
- **Link:** https://www.aliexpress.com/item/1005003299260311.html
- **Qty:** 4 · **Total:** €9.29 · **Status:** Completed (29 Apr 2026)
- **Specs:**
  - Size: 1 inch (25mm)
  - Type: Soft rubber universal swivel caster
  - Brake: Without brake
  - Use case: Platform trolley / robot base

---

## 🛠️ Tools

### 58-in-1 Electric Screwdriver Set
- **Store:** ETETS Store
- **Link:** https://www.aliexpress.com/item/1005005732530437.html
- **Qty:** 1 · **Total:** €18.33 · **Status:** Completed
- **Specs:**
  - Type: Precision electric screwdriver
  - Bits: 58-in-1
  - Power: Rechargeable (wireless)
  - Use case: Phone / watch / electronics repair

### 25-in-1 Mini Screwdriver Set
- **Store:** Shop1105071993 Store
- **Link:** https://www.aliexpress.com/item/1005010072165601.html
- **Qty:** 1 · **Total:** €3.49 · **Status:** Completed (29 Apr 2026)
- **Specs:**
  - Bits: 25-in-1
  - Type: Flat head + cross
  - Use case: Small electronics

### 80W Soldering Iron Kit (LCD, adjustable temp)
- **Store:** Shenzhen Lefavor tool's Store
- **Link:** https://www.aliexpress.com/item/1005005623832147.html
- **Qty:** 1 · **Total:** €4.99 · **Status:** Completed (29 Apr 2026)
- **Specs:**
  - Power: 80W
  - Display: LCD
  - Heater: Ceramic
  - Temperature: Adjustable
  - Includes: Soldering tips, tweezers, solder wire
  - Variant: 936R SET1, 220V EU Plug

### Soldering Iron Cleaning Ball (copper mesh)
- **Store:** Shenzhen Lefavor tool's Store
- **Link:** https://www.aliexpress.com/item/1005005623797293.html
- **Qty:** 1 · **Total:** €1.45 · **Status:** Completed
- **Specs:**
  - Type: Copper wire mesh cleaning ball
  - Function: Soldering tip cleaner (no water needed)

### ANENG SZ308 Digital Multimeter
- **Store:** ANENG Official Store
- **Link:** https://www.aliexpress.com/item/1005007530336684.html
- **Qty:** 1 · **Total:** €3.30 · **Status:** Completed
- **Specs:**
  - Model: ANENG SZ308
  - Measures: AC/DC current, voltage, resistance
  - Display: LCD
  - Features: Ohm, square wave test
  - Color: Black

### Digital Caliper 150mm (carbon fiber)
- **Store:** Dropshipping Factory Sales Store
- **Link:** https://www.aliexpress.com/item/1005007497369705.html
- **Qty:** 1 · **Total:** €2.76 · **Status:** Completed
- **Specs:**
  - Range: 0–150mm
  - Material: Carbon fiber
  - Display: Digital LCD
  - Resolution: 0.01mm

### Portable Digital Scale 10g–50kg
- **Store:** DIDA BEAR Official Store
- **Link:** https://www.aliexpress.com/item/1005007883367779.html
- **Qty:** 1 · **Total:** €3.19 · **Status:** Completed
- **Specs:**
  - Capacity: 10g–50kg
  - Display: LCD
  - Type: Hanging / luggage scale
  - Variant: Hook style

### PVC Cutting Mat A4 (black)
- **Store:** Shop1104120734 Store
- **Link:** https://www.aliexpress.com/item/1005007720373478.html
- **Qty:** 1 · **Total:** €1.45 · **Status:** Completed
- **Specs:**
  - Size: A4
  - Material: PVC
  - Color: Black
  - Use case: Cutting / engraving / DIY workbench

### Magnetic Phone Holder (MagSafe → 1/4" tripod)
- **Store:** Fomscvka Accessories Store
- **Link:** https://www.aliexpress.com/item/1005009320332284.html
- **Qty:** 1 · **Total:** €6.98 · **Status:** Completed (12 Nov 2025)
- **Specs:**
  - Type: MagSafe magnetic mount
  - Mount: 1/4" ARRI tripod thread
  - Compatible: iPhone 12–16
  - Color: Black

---

## 🧰 Consumables & Hardware

### Brass Heat Insert Nuts (270pcs M2/M3/M4)
- **Store:** XOPIP Official Store
- **Link:** https://www.aliexpress.com/item/1005006351445007.html
- **Qty:** 270 · **Total:** €3.88 · **Status:** Completed
- **Specs:**
  - Sizes: M2, M3, M4
  - Type: Knurled, double twill
  - Material: Brass
  - Use case: 3D printer embedded threads

### Heat Set Insert Nuts M2 B (500pcs)
- **Store:** Shop1105238119 Store
- **Link:** https://www.aliexpress.com/item/1005010436701150.html
- **Qty:** 500 · **Total:** €7.09 · **Status:** Completed (4 May 2026)
- **Specs:**
  - Size: M2 (type B)
  - Material: Stainless steel / brass
  - Use case: 3D printing / CNC

### Heat Set Insert Nuts (9-piece set, assorted)
- **Store:** Shop1105238119 Store
- **Link:** https://www.aliexpress.com/item/1005010436701150.html
- **Qty:** 1 set · **Total:** €10.76 · **Status:** Completed (3 May 2026)
- **Specs:**
  - Type: Assorted sizes (9-piece set)
  - Material: Stainless steel / brass

### Heat Shrink Tubing Kit (530pcs + heat gun)
- **Store:** Bluenglish Store
- **Link:** https://www.aliexpress.com/item/1005007103309007.html
- **Qty:** 530 + gun · **Total:** €6.69 · **Status:** Completed
- **Specs:**
  - Pieces: 530
  - Ratio: 2:1 shrink
  - Includes: 220V EU heat gun
  - Use case: Wire insulation / repair

### Nylon Cable Ties 3×150mm (100pcs, black)
- **Store:** EVERY DAY UP Store
- **Link:** https://www.aliexpress.com/item/1005007294796796.html
- **Qty:** 100 · **Total:** €1.44 · **Status:** Completed
- **Specs:**
  - Size: 3×150mm
  - Color: Black
  - Type: Self-locking

### Low Temp Solder Wire (20g, 1.0mm)
- **Store:** Little Angel Store
- **Link:** https://www.aliexpress.com/item/1005006892112907.html
- **Qty:** 20g · **Total:** €1.44 · **Status:** Completed
- **Specs:**
  - Weight: 20g
  - Diameter: 1.0mm
  - Type: Low-temperature, flux-cored
  - No solder powder needed

### Solder Paste Rosin Flux (10g)
- **Store:** BESTSELLER Chioce Store
- **Link:** https://www.aliexpress.com/item/1005008562727265.html
- **Qty:** 10g · **Total:** €2.09 · **Status:** Completed (29 Apr 2026)
- **Specs:**
  - Type: Lead-free rosin flux paste
  - Weight: 10g
  - Container: Plastic box

### 3M VHB Double Sided Tape (5pcs, 50×50mm)
- **Store:** Quick Shopping Store
- **Link:** https://www.aliexpress.com/item/1005008959170844.html
- **Qty:** 5 · **Total:** €2.03 · **Status:** Completed
- **Specs:**
  - Type: 3M VHB adhesive
  - Size: 50×50mm squares
  - Feature: High viscosity, waterproof

### Ultra-strong Adhesive Tape (1m, 20mm)
- **Store:** Hardware Polexin Store
- **Link:** https://www.aliexpress.com/item/1005006926453576.html
- **Qty:** 1m · **Total:** €1.35 · **Status:** Completed
- **Specs:**
  - Type: Monster tape (nano adhesive)
  - Width: 20mm
  - Thickness: 1mm
  - Feature: Waterproof, reusable

### Electrical Insulation Tape (10m, 16mm, black)
- **Store:** Shop1105133486 Store
- **Link:** https://www.aliexpress.com/item/1005010020553662.html
- **Qty:** 10m · **Total:** €1.25 · **Status:** Completed
- **Specs:**
  - Type: Flame retardant
  - Width: 16mm
  - Length: 10m (1 roll)
  - Feature: Waterproof, wire harness

### PCB Copper Clad Laminate 10×15cm (5pcs)
- **Store:** Electronic DIY Store
- **Link:** https://www.aliexpress.com/item/1005012282283549.html
- **Qty:** 5 · **Total:** €3.66 · **Status:** Completed
- **Specs:**
  - Size: 10×15cm
  - Type: Single-sided copper clad
  - Use case: DIY PCB etching

### Strong Disc Magnets (assorted sizes)
- **Store:** RefreshMyNest Store
- **Link:** https://www.aliexpress.com/item/1005009749865836.html
- **Qty:** 1 set · **Total:** €10.08 · **Status:** Completed
- **Specs:**
  - Type: Neodymium disc magnets
  - Sizes: 4×3, 5×2, 5×3, 6×3, 8×2, 10×2, 10×3mm
  - Use case: Fridge, construction, education, DIY

---

## 📋 Open Items

Things that need a meter or a look at the physical part, not a datasheet.

| # | Item | Why it matters |
|---|---|---|
| 1 | **XL4015 pot count** — one or two? | Two = CC/CV, charger plan works. One = CV-only, do not charge lithium with it |
| ~~2~~ | ~~**COB LED strip voltage**~~ | ✅ **ANSWERED 2026-08-26 — it is a 5V strip.** Full brightness on the 5V rail with the MOSFET bypassed. Now on its own MINI560 rail. See [`logs/012`](logs/012-2026-08-26-led-strip-ambient-brightness.md) |
| ~~3~~ | ~~MINI560 bench test~~ | ⬇️ **Demoted 2026-08-05** — MINI560 is no longer in the design. All 6 are spares. Only worth testing if a 5V rail comes back |
| ~~3~~ | ~~❓ **What supplies 5V now**~~ | ✅ **ANSWERED 2026-08-26.** Two rails: **LM2596S** → SG90 servos, **MINI560** → COB LED strip. Split because they interfered on one rail. See Power Rail Architecture |
| 11 | **COB LED strip current at full brightness** | Meter in series with the strip. Sizes the fuse and confirms the MINI560 headroom. Currently inferred only from a ~200 mV pack sag — **indirect** |
| 12 | **Is Teensy `VIN` wired to the LM2596S rail?** | ⚠️ Blocks the planned 6V servo change. **Teensy 4.1 VIN maximum is 5.5V** — 6V destroys the board |
| 4 | **Encoder wire colors on the actual motors** | Common scheme is blue = encoder VCC, red = motor. Legacy notes recorded red as encoder VCC. Wrong guess puts 12V into the encoder supply |
| 5 | **HC-SR04 board revision** | Listing says 5V; the Handson guide covers a 3.3–5V V2.0 board. Measure ECHO idle-high before wiring |
| ~~6~~ | ~~RPLIDAR C1 TX level~~ | ❌ **DELETED 2026-08-04** — lidar is on Jetson USB and never touches a Teensy pin |
| 7 | **Screen power draw** | Meter the panel's **own** supply. A prior session measured ~5.9W *total Jetson board* power running the face, but the panel is fed separately so it likely sits outside that figure |
| 8 | **Camera enumeration** | Set `uvcvideo quirks=128` **first**, then plug both OV9281s in and check `dmesg` for `Not enough bandwidth`. See Vision & Cameras |
| 9 | **36GP-555 stall current** | Not recorded here — the one hole in the power budget, exactly where the drive base sits. Sets the drive-motor fuse (20A is provisional) |
| 10 | **Which 5.5" panel is fitted** | The AM-OLED is listed *Pending* and the IPS as *BROKEN*. Touch does not enumerate at all — if the fitted panel is the broken IPS, that is the explanation. See Displays |

Tracked with dates and pass conditions in [`ACTION-PLAN.md`](ACTION-PLAN.md) section B.

### Migration notes — Arduino Nano → Teensy 4.1

Everything on the Teensy side lands at **3.3V**; the 5V and 12V rails carry power only. Changes from the legacy Nano build:

| What | Was | Becomes | Reason |
|---|---|---|---|
| IBT-2 header pin 7 (VCC) | Nano 5V | **Teensy 3.3V** | 74HC244 threshold is 3.5V at 5V VCC; Teensy outputs 3.3V |
| IBT-2 R_EN / L_EN | Nano 5V | **3.3V or GPIO** | 74HC244 absolute max is VCC + 0.5V |
| Motor PWM frequency | ~31.4 kHz | **20 kHz** | BTS7960 limit is 25 kHz |
| Encoder VCC | 5V | **3.3V** | output level follows supply; Teensy is not 5V tolerant |
| Ultrasonic | HC-SR04 @ 5V | **HC-SR04P @ 3.3V** | direct connect, no divider |
| Lidar | — | **Jetson USB, not the Teensy** | it has its own MCU; `Serial1` freed, MINI560 #1 freed, ripple limit gone |
| Servo power | Nano 5V | **12V power pack direct** (STS3215 bus servos) | arms are 12V bus servos, no 5V conversion involved. Nano 5V was never a valid supply for anything |
| Battery | one 3S pack | **two packs — 40T (35A) for power, 50E (10A) for electronics** | an arm stall tripping the 40A BMS cannot brown out the Jetson |

No level shifters anywhere in the robot.
