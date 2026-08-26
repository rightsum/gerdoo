/*
  led_strip_test — bench test for the COB strip on the LR7843 MOSFET module,
  plus a raw readout of the Keyestudio photoresistor.

  Standalone. Does not touch teensy_microros. Flash, watch, unflash.

  Wiring
    Teensy pin 4    -> LR7843 header PWM
    Teensy GND      -> LR7843 header GND   (not bonded to the power star ground)
    5V rail + fuse  -> LR7843 screw +
    strip +         -> LR7843 screw +      (same terminal)
    strip -         -> LR7843 screw LOAD
    LR7843 screw -  -> star ground

    photoresistor G -> Teensy GND
    photoresistor V -> Teensy 3.3V         (NOT 5V - the ADC is 0-3.3V)
    photoresistor S -> Teensy A1

  Console: 115200 on the Teensy's first serial port.
*/

const int LED_STRIP_PIN = 4;
const int LDR_PIN       = A1;
const int PWM_FREQ_HZ   = 20000;   // above audible, and no banding on the cameras
const int PWM_MAX       = 4095;    // 12-bit

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  analogWriteResolution(12);
  analogWriteFrequency(LED_STRIP_PIN, PWM_FREQ_HZ);
  pinMode(LED_STRIP_PIN, OUTPUT);
  analogWrite(LED_STRIP_PIN, 0);
}

void loop() {
  // Fixed steps rather than a smooth ramp, so a partial turn-on is obvious.
  const int levels[] = { 0, 410, 1024, 2048, 3072, PWM_MAX };
  const int n = sizeof(levels) / sizeof(levels[0]);

  for (int i = 0; i < n; i++) {
    analogWrite(LED_STRIP_PIN, levels[i]);

    // Sample the LDR a few times across the dwell so you can cover and
    // uncover the sensor and watch the number move in real time.
    for (int s = 0; s < 4; s++) {
      Serial.print("duty ");
      Serial.print(levels[i] * 100 / PWM_MAX);
      Serial.print("%\tldr ");
      Serial.println(analogRead(LDR_PIN));
      delay(500);
    }
  }
}
