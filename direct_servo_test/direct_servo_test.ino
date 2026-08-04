/*
  Direct Servo Test - No libraries, just raw digital pulses on D12

  Wiring (disconnect PCA9685 completely for this test):
    Nano 5V  -> Servo RED wire
    Nano GND -> Servo BLACK/BROWN wire
    Nano D12 -> Servo YELLOW/ORANGE/WHITE wire

  This sends standard 50 Hz servo pulses directly from the Nano.
  0°   = 0.5 ms pulse
  90°  = 1.5 ms pulse
  180° = 2.5 ms pulse

  If the servo sweeps, your servos are fine and the PCA9685 is the problem.
  If nothing happens, either servo is dead or USB can't supply enough current.
*/

const int SERVO_PIN = 12;

// Pulse widths in microseconds
const int PULSE_MIN = 500;   // 0 degrees
const int PULSE_MID = 1500;  // 90 degrees
const int PULSE_MAX = 2500;  // 180 degrees

void servoPulse(int pin, int microseconds) {
  digitalWrite(pin, HIGH);
  delayMicroseconds(microseconds);
  digitalWrite(pin, LOW);
}

void setup() {
  Serial.begin(9600);
  while (!Serial);

  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);

  Serial.println("=== Direct Servo Test ===");
  Serial.println("Wire ONE servo directly:");
  Serial.println("  RED    -> Nano 5V");
  Serial.println("  BLACK  -> Nano GND");
  Serial.println("  SIGNAL -> Nano D12");
  Serial.println("Servo should sweep every 3 seconds.\n");
}

void loop() {
  Serial.println("Moving to 0 degrees");
  for (int i = 0; i < 50; i++) {  // 50 pulses = 1 second at 50 Hz
    servoPulse(SERVO_PIN, PULSE_MIN);
    delay(20);
  }

  Serial.println("Moving to 90 degrees");
  for (int i = 0; i < 50; i++) {
    servoPulse(SERVO_PIN, PULSE_MID);
    delay(20);
  }

  Serial.println("Moving to 180 degrees");
  for (int i = 0; i < 50; i++) {
    servoPulse(SERVO_PIN, PULSE_MAX);
    delay(20);
  }

  Serial.println("Moving back to 0\n");
  for (int i = 0; i < 50; i++) {
    servoPulse(SERVO_PIN, PULSE_MIN);
    delay(20);
  }
}
