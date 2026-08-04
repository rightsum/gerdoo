/*
  Servo Pin Diagnostic

  This holds channel 0 at center position CONTINUOUSLY (no sweep).
  Use this to check voltage with a multimeter and verify servo wiring.

  What to check with a multimeter (while this sketch runs):
    1. PCA9685 big V+ terminal  -> GND terminal = should read ~5V
    2. Servo connector pin 1 (outside, toward board edge) -> pin 3 = ~5V
    3. Servo connector pin 2 (middle) -> pin 3 = should PULSE between 0V and ~5V

  Servo connector orientation on most PCA9685 boards:
    [SIGNAL  VCC  GND]  or  [GND  VCC  SIGNAL]
    Check the silkscreen near the header block!

  If voltage on pin 2 is flat 0V, the PCA9685 channel is not outputting.
  If voltage on pin 2 pulses but servo doesn't move, try swapping servo connector.
*/

#include <Wire.h>

#define PCA_ADDR 0x40

void pcaWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(PCA_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void setPWM(uint8_t ch, uint16_t off) {
  uint8_t reg = 0x06 + 4 * ch;
  Wire.beginTransmission(PCA_ADDR);
  Wire.write(reg);
  Wire.write(0);
  Wire.write(0);
  Wire.write(off & 0xFF);
  Wire.write(off >> 8);
  Wire.endTransmission();
}

void setup() {
  Serial.begin(9600);
  while (!Serial);

  Wire.begin();
  pcaWrite(0x00, 0x00);
  delay(5);
  pcaWrite(0x00, 0x10);
  delay(5);
  pcaWrite(0xFE, 121);
  delay(5);
  pcaWrite(0x00, 0xA0);
  delay(5);

  // Turn OFF all channels first
  for (int ch = 0; ch < 16; ch++) {
    setPWM(ch, 0);  // fully off
  }
  delay(1000);

  Serial.println("=== SERVO PIN DIAGNOSTIC ===");
  Serial.println("Channel 0 is now ON at center position (pulse ~1.5ms every 20ms).");
  Serial.println("Use a multimeter to check voltage on the servo connector pins.");
  Serial.println("Press RESET on Nano when done.\n");

  // Hold channel 0 at center continuously
  setPWM(0, 375);  // ~90 degrees
}

void loop() {
  // Just blink the built-in LED so you know the sketch is running
  digitalWrite(LED_BUILTIN, HIGH);
  delay(500);
  digitalWrite(LED_BUILTIN, LOW);
  delay(500);
}
