// Gerdoo's charging dock: ambient light in the sign head.
//
//   Gerdoo home (presence switch closed, 19 V on the plates)  -> green, a welcome sweep then a calm glow
//   Gerdoo away                                               -> amber, slow breathing ("waiting")
//
// Hardware (log 032):
//   19 V in (DC-022B, left side) -> spare XL4015 set to 5.0 V   (measure BEFORE connecting anything)
//   5 V -> Arduino Nano 5V pin, WS2812B strip +5V (1000 uF across the strip's supply)
//   D6 -> 330 R -> strip DIN      (18 LEDs, 60/m, stuck on the light box's inner front wall, facing back)
//   Plate + (after the presence microswitch) -> 100k -> A0 -> 33k -> GND
//       19.5 V on the plates reads ~4.8 V at A0. That line only exists while the robot presses the switch.
//
// Library: Adafruit NeoPixel (Library Manager).

#include <Adafruit_NeoPixel.h>

const uint8_t  PIN_STRIP  = 6;
const uint8_t  PIN_SENSE  = A0;
const uint16_t NUM_LEDS   = 18;
const float    DIVIDER    = (100.0 + 33.0) / 33.0;   // plate volts per ADC volt
const float    HOME_VOLTS = 12.0;                     // above this the robot is on the plates
const uint8_t  MAX_BRIGHT = 140;                      // of 255; ~0.4 A at full green on 18 LEDs

Adafruit_NeoPixel strip(NUM_LEDS, PIN_STRIP, NEO_GRB + NEO_KHZ800);

enum State { AWAY, HOME };
State state = AWAY;
uint32_t changedAt = 0;

float plateVolts() {
  long sum = 0;
  for (int i = 0; i < 8; i++) sum += analogRead(PIN_SENSE);
  return (sum / 8.0) * (5.0 / 1023.0) * DIVIDER;
}

void fill(uint8_t r, uint8_t g, uint8_t b, float level) {
  level = constrain(level, 0.0, 1.0);
  for (uint16_t i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, r * level, g * level, b * level);
  strip.show();
}

void setup() {
  strip.begin();
  strip.setBrightness(MAX_BRIGHT);
  fill(0, 0, 0, 0);
}

void loop() {
  // debounce: the switch has to agree for 300 ms before the colour changes
  static uint32_t agreeSince = 0;
  State seen = plateVolts() > HOME_VOLTS ? HOME : AWAY;
  if (seen == state) agreeSince = millis();
  else if (millis() - agreeSince > 300) { state = seen; changedAt = millis(); }

  uint32_t t = millis() - changedAt;
  if (state == HOME) {
    if (t < 900) {                                   // welcome: green sweeps out from the middle
      float reach = t / 900.0 * (NUM_LEDS / 2.0);
      for (uint16_t i = 0; i < NUM_LEDS; i++) {
        float d = fabs(i - (NUM_LEDS - 1) / 2.0);
        float v = constrain(reach - d + 1.0, 0.0, 1.0);
        strip.setPixelColor(i, 0, 255 * v, 60 * v);
      }
      strip.show();
    } else {
      float glow = 0.85 + 0.15 * sin(t / 2500.0 * 2 * PI);   // barely-there breathing
      fill(0, 255, 60, glow);
    }
  } else {
    float breathe = 0.25 + 0.75 * (0.5 - 0.5 * cos(t / 4000.0 * 2 * PI));   // 4 s amber breath
    fill(255, 140, 0, breathe);
  }
  delay(20);
}
