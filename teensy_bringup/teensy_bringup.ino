/*
  Teensy 4.1 bring-up / health check

  Step 1 of the Teensy migration. No peripherals are touched: nothing is
  wired yet, and until the bench measurements are
  done, driving any pin risks pushing 5V into a part that clamps at 3.6V.

  This firmware only proves the link is healthy:
    - USB Type must be Serial, so the board enumerates as 16c0:0483 and
      Linux creates /dev/ttyACM0. The board previously ran RawHID (16c0:0486)
      which offers no CDC interface at all, so no serial port could exist.
    - Answers a line protocol so the Jetson can verify the link both ways.
    - Reports the numbers that say whether the board is actually well:
      temperature, uptime, restart cause, loop rate.

  Protocol: newline-terminated ASCII, 115200 baud (rate is ignored by USB
  CDC, but it keeps the host tooling happy). Every reply is one line and
  starts with a tag, so a parser never has to guess.

    PING   -> PONG <millis>
    INFO   -> INFO <k>=<v> ...     firmware, board, clock, serial number
    HEALTH -> HEALTH <k>=<v> ...   temp, uptime, loop rate, restart cause
    ECHO x -> ECHO x               round-trip integrity check
    HELP   -> HELP ...
    <other>-> ERR unknown_command <cmd>

  Unsolicited: a HEARTBEAT line every 1000 ms, so a silent link is
  distinguishable from a wedged one without polling.
*/

// No external libraries. Temperature comes from tempmonGetTemp(), which the
// Teensy 4 core provides for the i.MX RT1062 on-die sensor, and the serial
// number from the OCOTP fuses — both are already in the core headers.

const char *FW_VERSION = "bringup-0.1.0";
const uint32_t HEARTBEAT_MS = 1000;

// Pin 13 is the onboard LED. It is the only pin this firmware drives, and it
// is safe: it goes nowhere but the LED.
const int LED_PIN = 13;

uint32_t bootMillis = 0;
uint32_t lastHeartbeat = 0;
uint32_t loopCount = 0;
uint32_t loopsPerSec = 0;
uint32_t lastRateCalc = 0;
uint32_t heartbeatSeq = 0;

char cmdBuf[128];
uint8_t cmdLen = 0;

// The i.MX RT1062 latches why it last came out of reset. A board that is
// silently rebooting under load looks identical to a healthy one over USB,
// because the CDC link re-enumerates fast enough to miss. This is the only
// way to tell the difference, so it is worth reporting on every HEALTH.
const char *restartCause() {
  uint32_t s = SRC_SRSR;
  if (s & (1 << 6)) return "temp_panic";
  if (s & (1 << 5)) return "watchdog3";
  if (s & (1 << 4)) return "jtag_sw";
  if (s & (1 << 3)) return "jtag_hw";
  if (s & (1 << 2)) return "watchdog";
  if (s & (1 << 1)) return "lockup";
  if (s & (1 << 0)) return "power_on";
  return "unknown";
}

// Teensy 4.1 serial number, same value lsusb reports. Lets the Jetson tell
// two boards apart once the arm controller is added.
uint32_t teensySerial() {
  return HW_OCOTP_MAC0 & 0xFFFFFF;
}

void sendInfo() {
  Serial.print("INFO fw=");
  Serial.print(FW_VERSION);
  Serial.print(" board=teensy41");
  Serial.print(" mcu=imxrt1062");
  Serial.print(" cpu_hz=");
  Serial.print(F_CPU_ACTUAL);
  Serial.print(" serial=");
  Serial.print(teensySerial());
  Serial.print(" usb=serial");
  Serial.print(" built=" __DATE__ " " __TIME__);
  Serial.println();
}

void sendHealth() {
  uint32_t up = millis() - bootMillis;
  Serial.print("HEALTH temp_c=");
  Serial.print(tempmonGetTemp(), 1);
  Serial.print(" uptime_ms=");
  Serial.print(up);
  Serial.print(" loop_hz=");
  Serial.print(loopsPerSec);
  Serial.print(" restart=");
  Serial.print(restartCause());
  Serial.print(" heartbeats=");
  Serial.print(heartbeatSeq);
  Serial.println();
}

void handleCommand(char *cmd) {
  // Trim trailing CR so both \n and \r\n hosts work.
  size_t n = strlen(cmd);
  while (n > 0 && (cmd[n - 1] == '\r' || cmd[n - 1] == ' ')) cmd[--n] = '\0';
  if (n == 0) return;

  if (strcmp(cmd, "PING") == 0) {
    Serial.print("PONG ");
    Serial.println(millis());
  } else if (strcmp(cmd, "INFO") == 0) {
    sendInfo();
  } else if (strcmp(cmd, "HEALTH") == 0) {
    sendHealth();
  } else if (strncmp(cmd, "ECHO ", 5) == 0) {
    Serial.print("ECHO ");
    Serial.println(cmd + 5);
  } else if (strcmp(cmd, "HELP") == 0) {
    Serial.println("HELP PING INFO HEALTH ECHO <text> HELP");
  } else {
    Serial.print("ERR unknown_command ");
    Serial.println(cmd);
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);

  // No `while (!Serial)` here. On the Nano that wait was harmless, but this
  // board runs headless on the robot: blocking on a host that may never open
  // the port would hang the firmware before it could report anything.
  bootMillis = millis();
  lastRateCalc = bootMillis;
  lastHeartbeat = bootMillis;

  Serial.println();
  Serial.println("BOOT teensy41 bringup");
  sendInfo();
}

void loop() {
  loopCount++;

  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      cmdBuf[cmdLen] = '\0';
      handleCommand(cmdBuf);
      cmdLen = 0;
    } else if (cmdLen < sizeof(cmdBuf) - 1) {
      cmdBuf[cmdLen++] = c;
    } else {
      // Overlong line: drop it and say so rather than silently truncating.
      cmdLen = 0;
      Serial.println("ERR line_too_long");
    }
  }

  uint32_t now = millis();

  if (now - lastRateCalc >= 1000) {
    loopsPerSec = loopCount;
    loopCount = 0;
    lastRateCalc = now;
  }

  if (now - lastHeartbeat >= HEARTBEAT_MS) {
    lastHeartbeat = now;
    heartbeatSeq++;
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    Serial.print("HEARTBEAT seq=");
    Serial.print(heartbeatSeq);
    Serial.print(" uptime_ms=");
    Serial.print(now - bootMillis);
    Serial.print(" temp_c=");
    Serial.print(tempmonGetTemp(), 1);
    Serial.print(" loop_hz=");
    Serial.print(loopsPerSec);
    Serial.println();
  }
}
