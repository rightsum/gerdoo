# Robot Project Context — LLM Prompt

Copy everything below into your preferred LLM to give it full context about your robot project.

---

You are helping me build a robot. Here is the complete context of my project:

## Brain
- NVIDIA Jetson Orin Nano Super (67 TOPS, 8GB LPDDR5, 6-core Arm A78AE @ 1.7GHz, Ampere GPU with 1024 CUDA cores)
- Runs AI workloads: vision (object detection, SLAM), LLMs, VLMs
- Storage: Crucial P310 1TB NVMe SSD (PCIe Gen4, 7100/6000 MB/s)
- WiFi: Bingfu dual-band 2.4/5/5.8GHz antenna set (3dBi, M.2 NGFF U.FL pigtails)
- Power: Waveshare UPS Module (C) for Jetson Orin with 21700 battery backup

## Co-processor
- Teensy 4.1 (with pins) — NXP i.MX RT1062, ARM Cortex-M7 @ 600MHz
- 8MB flash, 1MB RAM, 55 I/O pins, 8 UART, 3 SPI, 3 I2C, 3 CAN Bus, 4 quadrature decoders
- Powered by Jetson via USB (5V, ~100mA) — also serves as USB data link
- Handles real-time: motor PWM, servo control, encoder reading, sensor I2C/SPI/analog

## Power System
- Battery: 4× Samsung INR21700-50E (5000mAh, 10A drain) for logic + 4× Samsung INR21700-40T (4000mAh, 35A drain) for motors
- 3S configuration (~12.6V full, 10.8V nominal)
- BMS: 3S 40A (Heltec, 2× units pending delivery)
- 1S 21700 holders (4×, for individual cell mounting)
- Buck converter: 1× AZDelivery LM2596S with built-in voltmeter (chosen over Mini560 because LM2596S survives servo current spikes without latching off; Mini560 shuts down on transient overcurrent and requires manual power cycle)
- Boost converters: 5× MT3608 (step-up), 10× DC-DC step-up charger modules
- Power connectors: DC-022B jacks (10pcs, 5.5×2.5mm), DC extension cables (2×, 1m 22AWG), T-plug/Deans connectors (6× Y-splitter + 4× pigtail), pogo pins (2×, 5A)
- MOSFET: Isolated LR7843 module for high-power switching
- Diodes: 50× 10A10 rectifier diodes

## Power Distribution
```
3S Battery (12V)
├────► LM2596S 5V ──► RPLIDAR C1 (230mA, 800mA startup)
│                  ──► 2× SG90 servos (pan/tilt gimbal, 1.4A peak)
│                  ──► COB LED strip (300mA)
│                  [voltmeter shows battery voltage]
│
├────► Jetson (via Waveshare UPS / DC jack, 19V 45W supply)
│         └──► USB ──► Teensy 4.1 (100mA + data link)
│
├────► BTS7960 H-bridges (×2) ──► 36GP-555 motors (×2, 12V, 160RPM, with Hall encoders)
│                                  [powered directly from battery, 35A cells]
│
└────► STS3215 TTL bus servos (×3, 12V) via Waveshare Serial Bus Servo Driver
       [powered from battery, 12V — these are for SO-ARM100/LeRobot arm]
```

## Vision
- 2× OV9281 Global Shutter USB Camera (monochrome, 1280×720, 120fps, no rolling distortion) — for stereo vision / robot perception
- 1× Logitech Brio 500 (1080p Full HD, auto light correction, dual noise-cancelling mics, USB-C) — for teleoperation/video streaming

## Navigation
- RPLIDAR C1 (C1M1-R2) — SLAMTEC DTOF 360° laser scanner, 12m range, 5KHz sample rate, 0.72° angular resolution, TTL UART @ 460800 baud, 5V 230mA, IP54, ROS/ROS2 SDK

## Displays
- 5.5" AM-OLED 1920×1080 touchscreen (Wisecoco, pending delivery — replacement for broken IPS display) — connects to Jetson via DisplayPort/HDMI
- ESP32 Dev Board 2.8" LCD Touch Screen (CCSN SAMA) — standalone display/control
- 1.69" LCD IPS 240×280 ST7789V2 (SPI) — small status display, compatible with Teensy/ESP32/RPi
- DisplayPort → HDMI adapter (4K)
- UPERFECT VESA monitor stand (for development)

## Servos & Motor Control
- 3× FEETECH STS3215 (12V, 30kg·cm, TTL serial bus, metal gears) — for SO-ARM100/LeRobot robot arm (refunded by AliExpress but item received)
- Waveshare Serial Bus Servo Driver Board (ST/SC compatible, for RPi GPIO) — drives STS3215 servos
- PCA9685 16-Channel 12-bit PWM Servo Driver (I2C) — drives standard RC servos from Teensy
- DC Dual Servo Gimbal Pan/Tilt Bracket + 2× SG90 9G servos (29×29mm, 4.8-5V) — camera pan/tilt
- 2× 36GP-555 Planetary Gear Motor (12V, 160RPM, all-metal gears, Hall effect encoder + fixed bracket) — robot drive motors
- 2× Double BTS7960 43A H-Bridge Motor Driver (5.5-27V, PWM+DIR control) — bidirectional motor control

## Sensors
- 2× HC-SR04 ultrasonic distance sensor (2cm-400cm, 5V, trigger/echo)
- 2× HC-SR04P ultrasonic sensor (wide voltage 3-5.5V, 3.3V compatible)
- 1× AM2302/DHT22 temperature & humidity sensor (-40 to +80°C, 0-100% RH, single-wire)
- 5× Voltage sensor module (0-25V DC, analog divider output) — battery monitoring via Teensy ADC

## Wheels
- 1/10 RC drift car tires + alloy wheels (black, compatible HSP/Tamiya TT02/HPI/Kyosho)
- 4× 12mm wheel hex coupling brass adapter (8mm short style)
- 2× 65mm robot wheel tires (high friction, 1/10 scale)
- 4× furniture caster wheels (1 inch, soft rubber, swivel, no brake) — robot base

## Audio
- NBFINE USB PC speaker (mini soundbar, clip-on, USB plug-and-play) — robot audio output

## Lighting
- COB LED strip (magnetic mount, 2.2mm) — robot illumination

## Cables & Connectors
- USB Hub 3.0 4-port splitter (9-24V powered, for RPi/Jetson) — pending delivery
- 240W 40Gbps USB-C to USB-C cable (90° angle)
- FPV USB 3.1 Type-C 90° to USB-A FPC ribbon cable (30cm)
- FPV HDMI 90° FPC ribbon cable (30cm, 20-pin)
- Soft flat USB2.0 charging/data cord (30cm)
- 10× servo extension cables (150-500mm, Futaba JR)
- 100× Dupont jumper wires F-F (20cm, 2.54mm)
- DC power cables, jacks, pogo pins, T-plug/Deans connectors (see Power section)

## Tools
- 58-in-1 electric screwdriver set (rechargeable)
- 25-in-1 mini screwdriver set
- 80W soldering iron kit (LCD, adjustable temp, ceramic heater, 220V EU)
- Soldering iron cleaning ball (copper mesh)
- ANENG SZ308 digital multimeter
- Digital caliper 150mm (carbon fiber)
- Portable digital scale 10g-50kg
- PVC cutting mat A4

## Consumables
- 270× brass heat insert nuts (M2/M3/M4, knurled)
- 500× heat set insert nuts M2 type B
- 9-piece assorted heat set insert nut set
- 530× heat shrink tubing kit + 220V EU heat gun
- 100× nylon cable ties (3×150mm, black)
- 20g low-temp solder wire (1.0mm, flux-cored)
- 10g solder paste rosin flux
- 3M VHB double-sided tape (5× 50×50mm)
- Ultra-strong adhesive tape (1m, 20mm)
- Electrical insulation tape (10m, 16mm, flame retardant)
- 5× PCB copper clad laminate (10×15cm, single-sided)
- Strong neodymium disc magnets (assorted sizes: 4×3 to 10×3mm)

## Architecture Summary
- **Jetson Orin Nano Super** = AI brain (vision, navigation, decision-making)
- **Teensy 4.1** = real-time controller (motors, servos, encoders, sensors)
- **LM2596S** = 5V rail for LIDAR + pan/tilt servos + LED (chosen for surge tolerance)
- **Jetson USB** = powers Teensy (clean 5V, isolated from servo noise)
- **Battery direct** = motors (BTS7960) + STS3215 arm servos (12V)
- **3S 21700 pack** = 4× high-capacity (logic) + 4× high-drain (motors)

## Key Design Decisions
1. Teensy powered from Jetson USB — avoids servo noise on the Teensy power rail
2. LM2596S chosen over Mini560 — Mini560 latches off on servo current spikes, LM2596S rides through them
3. Separate battery cell types: 50E (10A) for logic longevity, 40T (35A) for motor current demands
4. RPLIDAR on LM2596S rail (not Jetson USB) — isolates USB bus from LIDAR's 800mA startup surge
5. OV9281 global shutter cameras (not rolling shutter) — no motion distortion for robot vision