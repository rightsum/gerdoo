# Servo problem — seeking second opinion

## Setup

- Robot with a 5.5" screen on a pan/tilt gimbal bracket
- 2× SG90 servos: one for pan (left/right), one for tilt (up/down)
- Servos powered by LM2596S buck converter: 12.6V 3S Li-ion battery → 5V output
- Servo signal wires connected to a Teensy 4.1 microcontroller:
  - Pan servo signal → Teensy pin 2
  - Tilt servo signal → Teensy pin 3
- Common ground: LM2596S GND + Teensy GND + battery negative all connected
- Teensy runs Arduino Servo library, generates 50Hz PWM (1-2ms pulse)
- Servo positions limited to 30-150° in firmware (20° was tested earlier, now 30°)

## What happened

1. An aggressive sweep test was run that moved both servos from 0° to 180° and back
2. The user reported it was "too harsh" and "close to breaking the screen"
3. After the sweep, the tilt servo stopped working correctly

## Symptoms (tilt servo)

- **When servo is unplugged (no power):** The screen can be moved freely by hand to any position, including fully upright
- **When servo is plugged in (power on):** The servo drives the screen FAST and HARD to the fully DOWN position and locks there
- **When position commands are sent (tilt=30, tilt=150, etc.):** The servo does NOT respond — it stays locked at the down position. Sometimes a gear-spinning sound is heard but no movement occurs
- **When trying to move the screen by hand while powered:** The servo resists firmly (locked) — can't be moved by hand
- **The pan servo works perfectly** on its pin (pin 2) — responds to all commands

## Diagnostic tests performed

### Test 1: Swap signal wires between pan and tilt servos
- Moved tilt servo signal to pin 2 (where pan servo was working)
- Moved pan servo signal to pin 3 (where tilt servo was)

Results:
- **Pan servo on pin 3:** WORKED — responded to tilt commands, moved correctly
- **Tilt servo on pin 2:** Did NOT work — felt like no signal at all, servo was free-moving (not locked)

This proves:
- Pin 2 outputs valid PWM ✅ (pan servo works there, and tilt servo doesn't lock there)
- Pin 3 outputs valid PWM ✅ (pan servo works there too)
- The tilt servo behaves DIFFERENTLY on different pins:
  - On pin 3: LOCKS hard at "down" position, motor actively driving
  - On pin 2: No lock, feels like dead/no signal

### Test 2: Swapped wires back to original positions
- Tilt servo back on pin 3, pan servo back on pin 2
- Result: Tilt servo NO LONGER locks (previously it locked on pin 3, now it doesn't)

This suggests the motor may have burned out from prolonged stalling during debugging, but raises the question: why did it behave differently on pin 2 vs pin 3 during the swap test?

## Key observations that are hard to explain

1. **If the servo motor is dead (burned out):** Why did it lock on pin 3 but feel free on pin 2 during the swap test? A dead motor should feel free on ALL pins.

2. **If the servo is on the wrong pin:** We confirmed the signal wire IS on pin 3, and the pan servo works on pin 3, so pin 3 is outputting valid PWM. The tilt servo doesn't respond to it.

3. **If the potentiometer is damaged:** The servo's internal position sensor may be stuck, causing the motor to drive continuously in one direction (to the mechanical stop at "down"). But then why did it feel "free" (no lock) when moved to pin 2?

4. **If the motor burned out during debugging:** The lock on pin 3 happened FIRST, then we spent time debugging (motor stalling for minutes), then swapped to pin 2 (motor already dead = no lock), then swapped back to pin 3 (still dead = no lock). This timeline is consistent but the user is skeptical.

## Questions for the second opinion

1. What could cause a servo to LOCK on one pin but feel FREE (no signal) on another pin, when both pins are proven to output valid PWM signals?

2. Is the potentiometer damage theory consistent with the observed behavior? If the pot is stuck, would the servo lock on one pin but not another?

3. Could the aggressive 0-180° sweep have damaged the servo in a way that causes it to respond to some PWM signals but not others?

4. Is the "motor burned out from stalling" timeline the most likely explanation, or is there another theory that better fits all the observations?

5. Could there be a difference in the PWM signal between pin 2 and pin 3 on a Teensy 4.1 that would cause a damaged servo to respond differently?

## Hardware specs

- Servo: SG90, 9g micro servo, plastic gears, 1.2 kg·cm torque, 4.8-6V, standard PWM (50Hz, 500-2500µs)
- MCU: Teensy 4.1 (NXP i.MX RT1062, 600MHz ARM Cortex-M7)
- Servo library: Arduino Servo library ( Teensyduino )
- Power: LM2596S buck converter, 12.6V → 5V, 3A capacity
- Load: 5.5" display screen on a pan/tilt gimbal bracket