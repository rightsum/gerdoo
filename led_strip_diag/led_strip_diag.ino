/*
  led_strip_diag — slow, steady ON/OFF for debugging with a multimeter.

  20 kHz PWM makes a DC meter read a time-average, so every measurement during
  fault-finding is a lie. This drives plain digital output: 5s LOW, 5s HIGH.

  Pin 13 (the onboard LED) mirrors the phase, so the board itself tells you the
  sketch is alive without a meter or a console.

  Pins 5 and 6 mirror pin 4 as spares — if pin 4 measures dead while 5 and 6
  swing, pin 4 is damaged and the signal wire just moves over.
*/

const int LED_STRIP_PIN = 4;
const int SPARE_A       = 5;
const int SPARE_B       = 6;
const int ONBOARD_LED   = 13;
const int LDR_PIN       = A1;

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(LED_STRIP_PIN, OUTPUT);
  pinMode(SPARE_A,       OUTPUT);
  pinMode(SPARE_B,       OUTPUT);
  pinMode(ONBOARD_LED,   OUTPUT);
}

void phase(const char *label, int level) {
  digitalWrite(LED_STRIP_PIN, level);
  digitalWrite(SPARE_A,       level);
  digitalWrite(SPARE_B,       level);
  digitalWrite(ONBOARD_LED,   level);
  for (int i = 0; i < 5; i++) {
    Serial.print(label);
    Serial.print("  ldr ");
    Serial.println(analogRead(LDR_PIN));
    delay(1000);
  }
}

void loop() {
  phase("pins 4/5/6 = LOW   onboard LED OFF ", LOW);
  phase("pins 4/5/6 = HIGH  onboard LED ON  ", HIGH);
}
