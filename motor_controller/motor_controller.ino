#include <Wire.h>

/*
  Motor Controller + Servo Test - Differential Drive Robot

  Hardware connections (Option 2 - ultrasonic PWM):
    D11 - Left Motor Forward  (Timer2, RPWM)
    D3  - Left Motor Backward (Timer2, LPWM)
    D10 - Right Motor Forward (Timer1, RPWM)
    D9  - Right Motor Backward (Timer1, LPWM)
    D2  - Left Encoder Channel A (Hardware Interrupt)
    D4  - Left Encoder Channel B
    D8  - Right Encoder Channel A (PinChangeInterrupt)
    D7  - Right Encoder Channel B
    A4  - PCA9685 SDA
    A5  - PCA9685 SCL

  Serial commands (9600 baud):
    F [speed]  Forward
    B [speed]  Backward
    L [speed]  Turn Left  (spin in place)
    R [speed]  Turn Right (spin in place)
    S          Stop
    P          Pan servo (ch0) center-sweep test
    T          Tilt servo (ch1) center-sweep test
    +          Increase default speed by 25
    -          Decrease default speed by 25
    H          Print help

  Speed range: 0 - 255
*/

// PCA9685 registers
#define PCA_ADDR 0x40
const int PAN_CH  = 0;
const int TILT_CH = 1;
const int SERVO_MIN = 150;
const int SERVO_MID = 375;
const int SERVO_MAX = 600;

// Motor pins
const int LEFT_FORWARD = 11;    // D11 (Timer2)
const int LEFT_BACKWARD = 3;    // D3  (Timer2)
const int RIGHT_FORWARD = 10;   // D10 (Timer1)
const int RIGHT_BACKWARD = 9;   // D9  (Timer1)

// Encoder pins (optional, for future use)
const int LEFT_ENC_A = 2;
const int LEFT_ENC_B = 4;
const int RIGHT_ENC_A = 8;     // was D3, moved to D8 for PinChangeInterrupt
const int RIGHT_ENC_B = 7;

// Default speed when no value is given (0-255)
int motorSpeed = 200;

void setup() {
  Serial.begin(9600);
  while (!Serial);  // wait for serial port (needed on some Nano boards)

  // Set Timer1 (D9/D10) PWM to ~31.4 kHz phase-correct (inaudible)
  TCCR1B = (TCCR1B & B11111000) | B00000001;

  // Set Timer2 (D3/D11) PWM to ~31.4 kHz phase-correct (inaudible)
  // Was fast PWM 62.5 kHz — changed to phase-correct to match Timer1
  TCCR2B = (TCCR2B & B11111000) | B00000001;  // prescaler = 1
  TCCR2A = (TCCR2A & B11111100) | B00000001;  // mode 1: phase-correct PWM

  // Init PCA9685 servo driver
  Wire.begin();
  pcaWrite(0x00, 0x00);   // MODE1 normal
  delay(5);
  pcaWrite(0x00, 0x10);   // sleep
  delay(5);
  pcaWrite(0xFE, 121);    // prescale ~50 Hz
  delay(5);
  pcaWrite(0x00, 0xA0);   // restart + normal + auto-increment
  delay(5);
  pcaSetPWM(PAN_CH,  SERVO_MID);
  pcaSetPWM(TILT_CH, SERVO_MID);

  pinMode(LEFT_FORWARD, OUTPUT);
  pinMode(LEFT_BACKWARD, OUTPUT);
  pinMode(RIGHT_FORWARD, OUTPUT);
  pinMode(RIGHT_BACKWARD, OUTPUT);

  stopMotors();
  printHelp();
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    char cmd = toupper(line[0]);
    int cmdSpeed = motorSpeed;

    // Parse optional speed after a space, e.g. "F 150"
    int spaceIdx = line.indexOf(' ');
    if (spaceIdx > 0) {
      int parsed = line.substring(spaceIdx + 1).toInt();
      if (parsed >= 0 && parsed <= 255) {
        cmdSpeed = parsed;
      }
    }

    switch (cmd) {
      case 'F': driveForward(cmdSpeed);  break;
      case 'B': driveBackward(cmdSpeed); break;
      case 'L': turnLeft(cmdSpeed);      break;
      case 'R': turnRight(cmdSpeed);     break;
      case 'S': stopMotors();            break;
      case 'P': testServo(PAN_CH);      break;  // pan servo sweep
      case 'I': testServo(TILT_CH);     break;  // tilt servo sweep (I for tilt)
      case '+': adjustSpeed(25);         break;
      case '-': adjustSpeed(-25);        break;
      case 'D': runDiagnostic();         break;
      case 'H': printHelp();             break;
      default:
        Serial.println("Unknown command. Send H for help.");
        break;
    }
  }
}

/* --- motor primitives --- */

void setMotors(int leftFwd, int leftBck, int rightFwd, int rightBck) {
  analogWrite(LEFT_FORWARD,  constrain(leftFwd,  0, 255));
  analogWrite(LEFT_BACKWARD, constrain(leftBck,  0, 255));
  analogWrite(RIGHT_FORWARD, constrain(rightFwd, 0, 255));
  analogWrite(RIGHT_BACKWARD,constrain(rightBck, 0, 255));
}

void driveForward(int s) {
  Serial.print("Forward @ "); Serial.println(s);
  setMotors(s, 0, s, 0);
}

void driveBackward(int s) {
  Serial.print("Backward @ "); Serial.println(s);
  setMotors(0, s, 0, s);
}

// Spin left in place: left backward, right forward
void turnLeft(int s) {
  Serial.print("Turn Left @ "); Serial.println(s);
  setMotors(0, s, s, 0);
}

// Spin right in place: left forward, right backward
void turnRight(int s) {
  Serial.print("Turn Right @ "); Serial.println(s);
  setMotors(s, 0, 0, s);
}

void runDiagnostic() {
  Serial.println("\n=== DIAGNOSTIC: what kind of noise is this? ===");
  Serial.println("Listen carefully and compare...\n");

  // 1. Pure DC (no PWM switching at all)
  Serial.println("TEST 1: Full DC (255) — no PWM switching");
  Serial.println("        -> If still noisy = mechanical brushes/gearbox (normal for brushed)");
  setMotors(255, 0, 255, 0);
  delay(2500);
  stopMotors();
  delay(500);

  // 2. 50% PWM — maximum switching, most electrical noise if any
  Serial.println("TEST 2: 50% PWM (128) — maximum switching activity");
  Serial.println("        -> If MUCH noisier than Test 1 = PWM is contributing");
  setMotors(128, 0, 128, 0);
  delay(2500);
  stopMotors();
  delay(500);

  // 3. Low PWM — very choppy, clearly audible if PWM-related
  Serial.println("TEST 3: Low PWM (80) — low duty cycle");
  Serial.println("        -> If buzzy/whiny = PWM frequency or ceramic caps singing");
  setMotors(80, 0, 80, 0);
  delay(2500);
  stopMotors();
  delay(500);

  Serial.println("=== END DIAGNOSTIC ===");
  Serial.println("Tip: hold the motor body vs hold the driver board to locate the source.\n");
}

void stopMotors() {
  Serial.println("Stop");
  setMotors(0, 0, 0, 0);
}

void adjustSpeed(int delta) {
  motorSpeed = constrain(motorSpeed + delta, 0, 255);
  Serial.print("Default speed set to "); Serial.println(motorSpeed);
}

void printHelp() {
  Serial.println("=== Motor Controller Help ===");
  Serial.println("F [0-255]  Forward");
  Serial.println("B [0-255]  Backward");
  Serial.println("L [0-255]  Turn Left  (spin in place)");
  Serial.println("R [0-255]  Turn Right (spin in place)");
  Serial.println("S          Stop");
  Serial.println("P          Test Pan servo (ch0) sweep");
  Serial.println("I          Test Tilt servo (ch1) sweep");
  Serial.println("D          Run motor noise diagnostic");
  Serial.println("+          Increase default speed by 25");
  Serial.println("-          Decrease default speed by 25");
  Serial.println("H          Print this help");
  Serial.println("=============================");
}

/* --- PCA9685 servo helpers --- */

void pcaWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(PCA_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void pcaSetPWM(uint8_t ch, uint16_t off) {
  uint8_t reg = 0x06 + 4 * ch;
  Wire.beginTransmission(PCA_ADDR);
  Wire.write(reg);
  Wire.write(0);          // ON_L
  Wire.write(0);          // ON_H
  Wire.write(off & 0xFF); // OFF_L
  Wire.write(off >> 8);  // OFF_H
  Wire.endTransmission();
}

void testServo(uint8_t ch) {
  String name = (ch == PAN_CH) ? "Pan" : "Tilt";
  Serial.print("Testing "); Serial.print(name);
  Serial.println(" servo sweep...");

  Serial.println("  Center -> Min");
  for (int pos = SERVO_MID; pos >= SERVO_MIN; pos -= 5) {
    pcaSetPWM(ch, pos);
    delay(15);
  }

  Serial.println("  Min -> Max");
  for (int pos = SERVO_MIN; pos <= SERVO_MAX; pos += 5) {
    pcaSetPWM(ch, pos);
    delay(15);
  }

  Serial.println("  Max -> Center");
  for (int pos = SERVO_MAX; pos >= SERVO_MID; pos -= 5) {
    pcaSetPWM(ch, pos);
    delay(15);
  }

  Serial.println("  Done.");
}
