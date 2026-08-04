/*
  Encoder Test - Verify wiring and counting

  Hardware:
    D2  - Left Encoder Channel A (Hardware Interrupt INT0)
    D4  - Left Encoder Channel B
    D8  - Right Encoder Channel A (PinChangeInterrupt PCINT0)
    D7  - Right Encoder Channel B

  Upload, open serial monitor, then:
  1. Turn LEFT wheel by hand -> left count should change
  2. Turn RIGHT wheel by hand -> right count should change
  3. Spin a motor via keyboard/motor_controller -> counts should race upward

  One full wheel revolution typically gives 40-80 counts depending on the encoder PPR.
*/

volatile long leftCount = 0;
volatile long rightCount = 0;

// D2 = INT0 (left encoder A). In ISR we read D4 (B) for direction.
void leftISR() {
  uint8_t a = digitalRead(2);
  uint8_t b = digitalRead(4);
  // Quadrature direction: when A changes, if A==B we go one way, else the other.
  // The sign tells you if the encoder wiring is "forward-positive" or not.
  if (a == b) leftCount++; else leftCount--;
}

// D8 = PB0 = PCINT0. ISR fires on any Port B pin change.
ISR(PCINT0_vect) {
  uint8_t a = digitalRead(8);
  uint8_t b = digitalRead(7);
  if (a == b) rightCount++; else rightCount--;
}

void setup() {
  Serial.begin(9600);
  while (!Serial);

  // Pull-ups keep pins stable when encoder output is open-collector / floating.
  pinMode(2, INPUT_PULLUP);
  pinMode(4, INPUT_PULLUP);
  pinMode(8, INPUT_PULLUP);
  pinMode(7, INPUT_PULLUP);

  // Left encoder: hardware interrupt on D2 (INT0)
  attachInterrupt(digitalPinToInterrupt(2), leftISR, CHANGE);

  // Right encoder: PinChangeInterrupt on D8 (PB0 / PCINT0)
  PCICR  |= (1 << PCIE0);   // enable PCINT0 (Port B) interrupts
  PCMSK0 |= (1 << PCINT0);  // unmask only PB0 (D8)

  Serial.println("=== Encoder Test Started ===");
  Serial.println("Turn a wheel by hand. You should see counts change.");
  Serial.println("Forward should be POSITIVE, backward NEGATIVE.");
  Serial.println("============================================");
}

void loop() {
  static long lastL = 0;
  static long lastR = 0;

  noInterrupts();
  long l = leftCount;
  long r = rightCount;
  interrupts();

  if (l != lastL || r != lastR) {
    Serial.print("Left: ");
    Serial.print(l);
    Serial.print("  |  Right: ");
    Serial.println(r);
    lastL = l;
    lastR = r;
  }

  delay(50);  // 20 Hz print rate — responsive but not overwhelming
}
