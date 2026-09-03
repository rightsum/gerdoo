# Teensy 4.1 Pinout & Wiring Reference

> The Teensy 4.1 is the robot's real-time controller. It runs micro-ROS over USB
> (Dual Serial) and bridges sensors/actuators to ROS 2 on the Jetson.
>
> **ADC is 3.3V max — NOT 5V tolerant.** Every analog input must stay within 0–3.3V.

## Teensy 4.1 at a glance

| Resource | Detail |
|---|---|
| **MCU** | NXP i.MX RT1062, 600 MHz ARM Cortex-M7 |
| **Digital I/O** | 55 pins, 3.3V logic |
| **Analog Inputs** | 18 pins (A0–A17), 12-bit ADC, 0–3.3V |
| **PWM** | 35 pins, 22 independent frequency groups |
| **Serial (UART)** | 8 ports |
| **SPI** | 3 ports |
| **I2C** | 3 ports |
| **USB** | Dual Serial (`usb=serial2`): `if00` = console, `if02` = micro-ROS |
| **Flash** | 8 MB W25Q64JV (onboard) |
| **Power** | 5V via USB or VIN, ~100 mA @ 600 MHz |

## Device paths (on the Jetson)

```
/dev/serial/by-id/usb-Teensyduino_Dual_Serial_19627940-if00   ← console (Serial)
/dev/serial/by-id/usb-Teensyduino_Dual_Serial_19627940-if02   ← micro-ROS (SerialUSB1)
```

## Current wiring

| Pin | Function | Notes |
|---|---|---|
| **13** | Onboard LED | Status indicator, micro-ROS `/teensy/led` subscriber |
| **USB** | Dual Serial | Console + micro-ROS transport to Jetson |

**Everything else is unwired.** All analog, digital, PWM, UART, SPI, and I2C pins are available.

## Analog input assignments

| Pin | ADC | Function | Status |
|---|---|---|---|
| **A0** (pin 14) | ADC0 | Main battery voltage sensor | ✅ Live |
| **A1** (pin 15) | ADC1 | Ambient light sensor (Keyestudio photoresistor) | ✅ Live |
| A2–A17 | — | — | Available |

## PWM output assignments

| Pin | Function | Status |
|---|---|---|
| **2** | Neck pan servo (SG90, yaw) | ✅ Wired |
| **3** | Neck tilt servo (SG90, pitch) | ✅ Wired — **mounted reversed**, see below |
| **4** | COB LED strip via D4184 MOSFET module, 18 kHz | ✅ Wired |

### A0 — Main battery voltage sensor

**Module:** Voltage Sensor Module Max 25V (5pcs in inventory)
**Divider ratio:** 5:1 (30kΩ / 7.5kΩ)

**Module layout:** two sides —
- **Screw terminals** (battery input): VCC → battery +, GND → battery -
- **3-pin header** (to Teensy): S → A0, + → Teensy 3.3V, - → Teensy GND

| Module pin | Connects to | Voltage |
|---|---|---|
| Screw VCC | Main battery + terminal | 0–12.6V (3S Li-ion) |
| Screw GND | Battery negative / star ground | 0V |
| Header S | Teensy A0 (pin 14) | 0–2.52V (12.6V ÷ 5) |
| Header + | Teensy 3.3V | Powers module output circuit |
| Header - | Teensy GND | Common ground |

**Safe for Teensy:** 12.6V ÷ 5 = 2.52V, well within the 3.3V ADC limit.
**Resolution:** 3.3V / 4096 × 5 = ~4 mV at the battery (12-bit mode).

⚠️ **Common ground required:** Teensy GND must connect to the battery negative / star ground point. Without it, the ADC reads noise.

⚠️ **Do not exceed 16.5V on the module input** — that would put 3.3V on the ADC pin. A 3S pack maxes at 12.6V, so this is not a concern in practice.

⚠️ **ADC resolution:** The Teensy 4.1 defaults to 10-bit `analogRead()`. Must call `analogReadResolution(12)` in `setup()` to use the full 12-bit range — without it, raw values are 0–1023 but calculated as 0–4095, giving readings ~4× too low.

### Pin 4 / A1 — COB LED strip and ambient light

**Switch:** D4184 dual-MOSFET module (logic-level, 3.3V trigger, 15A). Low-side —
the module passes `VIN+` through to `OUT+` and chops `OUT-` against `VIN-`.

| Module terminal | Connects to |
|---|---|
| `VIN+` | 5V rail (LM2596S), through an inline fuse |
| `VIN-` | Star ground point |
| `OUT+` | LED strip `+` |
| `OUT-` | LED strip `−` |
| Header `PWM` | Teensy pin 4 |
| Header `GND` | Teensy GND |

**Sensor:** Keyestudio photoresistor module — the 10k half of the divider is onboard.

| Module pin | Connects to |
|---|---|
| `G` | Teensy GND |
| `V` | Teensy **3.3V** |
| `S` | Teensy A1 (pin 15) |

⚠️ **Power the sensor from 3.3V, never 5V.** Its `S` output is a divider off its own
supply, so a 5V module puts 5V on a 3.3V ADC pin.

⚠️ **An IRF520-based "MOS Module" will not work here.** Vgs(th) runs to 4V and Rds(on)
is specified at a 10V gate, so a 3.3V pin leaves it in the linear region — dim strip,
hot FET, or nothing at all. Use a logic-level part (D4184/AOD4184, IRLZ44N, IRLB8721).
See [`logs/012`](logs/012-2026-08-26-led-strip-ambient-brightness.md).

**PWM frequency: 18 kHz.** Inside the D4184's 0–20 kHz spec, above adult hearing so the
strip does not whine, and far above any camera shutter so it cannot band the OV9281s
or the Brio.

### Neck servos — centre, direction and motion

**Straight ahead is `pan=110 tilt=110`.** Measured on the robot, not the midpoint
of the servo range: the gimbal is not mounted symmetrically. The same pair is used
by the firmware's boot position, the panel's centre button and the face tracker.

⚠️ **The tilt servo is mounted reversed.** The firmware writes
`TILT_MAX + TILT_MIN - angle` via `writeTilt()`, and the face tracker applies a
second inversion on top (`tilt_inverted=True`). Both were established by watching
the real robot; neither is derivable.

⚠️ **The servos must be written explicitly in `setup()`.** The loop only writes on
change, so without a boot write they hold whatever position they powered up in
while the firmware reports the centre.

**Motion:** 50 Hz updates (an SG90 samples no faster), capped at 70 deg/s with an
exponential ease. Pan detaches after 1.5 s of stillness to stop it buzzing; tilt
stays energised because it carries the screen's weight.

See [`logs/017`](logs/017-2026-09-03-face-tracking.md).

## micro-ROS topics

| Topic | Type | Direction | Rate | Status |
|---|---|---|---|---|
| `/teensy/heartbeat` | `std_msgs/Int32` | Teensy → ROS | 1 Hz | ✅ Live |
| `/teensy/temperature` | `std_msgs/Float32` | Teensy → ROS | 1 Hz | ✅ Live |
| `/teensy/battery_main` | `std_msgs/Float32` | Teensy → ROS | 1 Hz | ✅ Live |
| `/teensy/light_level` | `std_msgs/Float32` | Teensy → ROS | 1 Hz | ✅ Live |
| `/teensy/led` | `std_msgs/Bool` | ROS → Teensy | on demand | ✅ Live |
| `/teensy/led_strip` | `std_msgs/Float32` | ROS → Teensy | on demand | ✅ Live |

`/teensy/light_level` is normalised 0–1 (0 = dark room, 1 = bright). `/teensy/led_strip`
takes 0–1 to force a brightness, or **any negative value to hand control back to the
light sensor**.

## Console commands

| Command | Response | Status |
|---|---|---|
| `PING` | `PONG` | ✅ |
| `INFO` | Firmware version, board, CPU | ✅ |
| `HEALTH` | Temp, uptime, loop rate, restart cause | ✅ |
| `ROS` | Agent state, connects, drops | ✅ |
| `BATTERY` | Main battery voltage, raw ADC, pin voltage | ✅ Live |
| `LIGHT` | LDR raw, normalised, calibration points, strip duty, mode | ✅ Live |
| `CAL dark` / `CAL bright` | Store the current LDR reading as that endpoint | ✅ Live |
| `STRIP auto` / `STRIP 0-100` | Follow the sensor, or force a brightness | ✅ Live |

## Wiring rules (from inventory.md)

1. **Star ground, not daisy chain.** Every return goes to one star point. Voltage drops in shared wires corrupt readings.
2. **Power rails carry power only — never a signal that touches the Teensy.** Everything on the Teensy side lands at 3.3V.
3. **No 5V on any Teensy pin.** The ADC is 0–3.3V. Digital pins are 3.3V logic, NOT 5V tolerant.
4. **VIN/USB power:** if Teensy VIN is ever fed from a buck while USB is also connected, cut the VUSB↔VIN pad on the board underside first.