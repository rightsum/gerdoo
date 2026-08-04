# Robot Pinout & Wiring Reference

## Arduino Nano

### Digital Pins

| Nano Pin | Connection | Notes |
|----------|-----------|-------|
| **D2** | Left Encoder Channel A | Hardware Interrupt (INT0) |
| **D3** | Left Motor Backward (LPWM) | Timer2, ~31.4 kHz PWM |
| **D4** | Left Encoder Channel B | Digital input |
| **D5** | *(available)* | Was left motor forward before rewire |
| **D6** | *(available)* | Was left motor backward before rewire |
| **D7** | Right Encoder Channel B | Digital input |
| **D8** | Right Encoder Channel A | PinChangeInterrupt (PCINT0) |
| **D9** | Right Motor Backward (LPWM) | Timer1, ~31.4 kHz PWM |
| **D10** | Right Motor Forward (RPWM) | Timer1, ~31.4 kHz PWM |
| **D11** | Left Motor Forward (RPWM) | Timer2, ~31.4 kHz PWM |
| **D12** | *(available)* | Good spare for direct servo tests |
| **D13** | Built-in LED | Used for status blinking |

### Analog Pins

| Nano Pin | Connection | Notes |
|----------|-----------|-------|
| **A0** | Battery Voltage Sensor | 30kΩ/7.5kΩ voltage divider |
| **A1** | *(available)* | |
| **A2** | *(available)* | |
| **A3** | *(available)* | |
| **A4** | PCA9685 SDA | I2C data, 4.7kΩ pull-up recommended |
| **A5** | PCA9685 SCL | I2C clock, 4.7kΩ pull-up recommended |

### Power Pins

| Nano Pin | Connection | Notes |
|----------|-----------|-------|
| **5V** | PCA9685 VCC (small pins) | Logic power for I2C chip |
| **5V** | PCA9685 V+ (big terminals) | **Servo motor power rail** |
| **5V** | Encoder VCC (both) | Encoder power |
| **GND** | Common ground rail | Everything shares this |
| **Vin** | *(unused)* | Powered via USB-C instead |

---

## Motor Drivers (IBT-2 / BTS7960)

### Left Motor Driver

| Driver Pin | Source | Notes |
|-----------|--------|-------|
| **B+ / B-** | 3S LiPo battery | High-current motor power |
| **M+ / M-** | Left motor | Thick wires to motor |
| **R_EN** | Nano 5V | Permanently enabled |
| **L_EN** | Nano 5V | Permanently enabled |
| **RPWM** | Nano **D11** | Forward PWM, Timer2 |
| **LPWM** | Nano **D3** | Backward PWM, Timer2 |
| **VCC** | Nano 5V | Logic power |
| **GND** | Common GND | |

### Right Motor Driver

| Driver Pin | Source | Notes |
|-----------|--------|-------|
| **B+ / B-** | 3S LiPo battery | High-current motor power |
| **M+ / M-** | Right motor | Thick wires to motor |
| **R_EN** | Nano 5V | Permanently enabled |
| **L_EN** | Nano 5V | Permanently enabled |
| **RPWM** | Nano **D10** | Forward PWM, Timer1 |
| **LPWM** | Nano **D9** | Backward PWM, Timer1 |
| **VCC** | Nano 5V | Logic power |
| **GND** | Common GND | |

---

## Wheel Encoders

### Left Encoder

| Encoder Wire | Nano Pin | Notes |
|-------------|----------|-------|
| **VCC** (Red) | 5V rail | |
| **GND** (Black) | GND rail | |
| **Channel A** (Green) | **D2** | Hardware Interrupt INT0 |
| **Channel B** (Yellow) | **D4** | Digital input |

### Right Encoder

| Encoder Wire | Nano Pin | Notes |
|-------------|----------|-------|
| **VCC** (Red) | 5V rail | |
| **GND** (Black) | GND rail | |
| **Channel A** (Green) | **D8** | PinChangeInterrupt PCINT0 |
| **Channel B** (Yellow) | **D7** | Digital input |

---

## PCA9685 Servo Driver Board

### Logic Side (small pins near SDA/SCL)

| PCA9685 Pin | Source | Notes |
|------------|--------|-------|
| **VCC** | Nano 5V | Powers the I2C chip, LED lights up |
| **GND** | Common GND | |
| **SDA** | Nano **A4** | I2C data |
| **SCL** | Nano **A5** | I2C clock |

### Servo Power Side (big terminals / barrel jack near large capacitor)

| PCA9685 Terminal | Source | Notes |
|-------------------|--------|-------|
| **V+** | Nano 5V **or** battery 5V buck | **THIS POWERS THE SERVOS** |
| **GND** | Common GND | |

> **CRITICAL:** The small VCC pins only run the I2C chip. The big V+/GND terminals actually drive current through the servos. If V+ is unwired, the board talks but servos sit dead.

### Servo Headers (16 channels, 0-15)

| Header | Typical Use | Pin Order |
|--------|-------------|-----------|
| **Channel 0** | Pan servo | Check silkscreen: usually [Signal, VCC, GND] or [GND, VCC, Signal] |
| **Channel 1** | Tilt servo | Same pin order as channel 0 |
| **Channels 2-15** | Available | |

Servo wire colors:
- **Black/Brown** → GND (outside pin)
- **Red** → VCC (middle pin)
- **Yellow/Orange/White** → Signal (single pin, check silkscreen)

---

## Battery Voltage Sensor

| Sensor Pin | Source | Notes |
|-----------|--------|-------|
| **VCC** | Battery + (via divider) | Through 30kΩ resistor |
| **Signal** | Nano **A0** | Between 30kΩ and 7.5kΩ resistors |
| **GND** | Battery - / Common GND | Through 7.5kΩ resistor |

---

## Power Architecture

```
USB-C (Nano)
    │
    ├── Nano 5V ──┬── PCA9685 VCC (logic)
    │              ├── PCA9685 V+ (servo power) ← CRITICAL
    │              ├── Encoder VCC (both)
    │              ├── IBT-2 VCC (both)
    │              └── R_EN / L_EN (both drivers)
    │
    └── Nano GND ──┬── Common ground rail
                   ├── PCA9685 GND
                   ├── Battery GND
                   ├── Encoder GND
                   └── IBT-2 GND

3S LiPo Battery
    │
    ├── B+ ─── IBT-2 B+ (both drivers)
    │
    └── B- ─── IBT-2 B- (both drivers)
               └── Common ground rail
```

---

## Pin Change History

| What | Original | After Option 2 (ultrasonic PWM) | Reason |
|------|----------|-------------------------------|--------|
| Left Motor Forward | D5 | **D11** | Timer2 channel B |
| Left Motor Backward | D6 | **D3** | Timer2 channel A |
| Right Encoder A | D3 | **D8** | Freed D3 for motor |
| Right Motor Forward | D9 | **D10** | Wiring swap |
| Right Motor Backward | D10 | **D9** | Wiring swap |

---

## Free Pins (available for expansion)

- **D5** (PWM capable)
- **D6** (PWM capable)
- **D12**
- **D13** (LED, but usable)
- **A1**
- **A2**
- **A3**

---

## Quick Troubleshooting

| Problem | Check |
|---------|-------|
| Motor doesn't spin | IBT-2 B+/B- connected to battery? R_EN/L_EN wired to 5V? |
| Motor spins wrong way | Swap RPWM/LPWM pins in code or swap M+/M- wires |
| Encoder doesn't count | VCC/GND on encoder? A channel on interrupt pin? |
| Servo doesn't move | **V+ terminal powered?** Servo connector not reversed? |
| PCA9685 not found | A4/A5 wired? I2C pull-ups (4.7kΩ) installed? |
| Upload fails | Try old bootloader: `arduino:avr:nano:cpu=atmega328old` |
| USB disconnects on servo test | Servos draw too much current — power V+ from battery buck |
