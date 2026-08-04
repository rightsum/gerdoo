/*
  Simple Battery Voltage Reader
  - Reads analog voltage from A0
  - Prints raw value and calculated voltage to Serial Monitor

  Hardware:
  - Arduino Nano
  - Voltage sensor connected to A0

  Calibration:
  Most battery voltage sensors use a voltage divider.
  Adjust the R1, R2 values and V_REF below to match your sensor.
*/

const int VOLTAGE_PIN = A0;

// Arduino Nano analog reference voltage (5V by default)
const float V_REF = 5.0;
const int ADC_RESOLUTION = 1023;

// Voltage divider resistors on your sensor module (ohms)
// Common modules: R1=30k, R2=7.5k  (divide-by-5)
// Adjust these if your sensor uses different values.
const float R1 = 30000.0;
const float R2 = 7500.0;

// Pre-calculate divider ratio
const float DIVIDER_RATIO = (R1 + R2) / R2;

void setup() {
  Serial.begin(9600);
  while (!Serial); // Wait for serial port to connect (needed for some Nano boards)
  
  Serial.println("Battery Voltage Monitor Started");
  Serial.println("-------------------------------");
}

void loop() {
  int rawValue = analogRead(VOLTAGE_PIN);

  // Convert raw ADC reading to voltage at the pin
  float pinVoltage = (rawValue / (float)ADC_RESOLUTION) * V_REF;

  // Scale back up to actual battery voltage using divider ratio
  float batteryVoltage = pinVoltage * DIVIDER_RATIO;

  Serial.print("Raw ADC: ");
  Serial.print(rawValue);
  Serial.print("  |  Pin Voltage: ");
  Serial.print(pinVoltage, 3);
  Serial.print(" V  |  Battery Voltage: ");
  Serial.print(batteryVoltage, 2);
  Serial.println(" V");

  delay(500);
}
