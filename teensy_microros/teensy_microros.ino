/*
  Teensy 4.1 — micro-ROS node over USB, with the debug console kept alive.

  Step 3: adds main battery voltage monitoring on A0 via a Voltage Sensor
  Module (Max 25V, 5:1 divider). The 3S pack (12.6V max) produces 2.52V on
  A0 — safely within the 3.3V ADC range.

  ---------------------------------------------------------------------------
  DUAL SERIAL — the reason this builds with usb=serial2
  ---------------------------------------------------------------------------
  micro-ROS consumes the serial port it runs on: that port becomes XRCE-DDS
  framing, so Serial.print debugging on it is impossible. On a robot still
  being brought up that is painful, and it is exactly what makes micro-ROS
  failures feel opaque.

  Teensy solves it for free. USB Type = Dual Serial gives two CDC interfaces:

    Serial      -> /dev/ttyACM0  human console. Same line protocol as
                                 teensy_bringup, so health_check.py still works.
    SerialUSB1  -> /dev/ttyACM1  micro-ROS transport. Agent attaches here.

  micro_ros_arduino's default transport is hardcoded to `Serial`
  (src/default_transport.cpp), but its four entry points are declared
  __attribute__((weak)). Defining strong versions below overrides them and
  moves micro-ROS onto SerialUSB1. No library edits, so an upgrade cannot
  silently revert this.

  ---------------------------------------------------------------------------
  ROS 2 interface
  ---------------------------------------------------------------------------
    publish   /teensy/heartbeat      std_msgs/Int32     seq, 1 Hz
    publish   /teensy/temperature    std_msgs/Float32   die temp C, 1 Hz
    publish   /teensy/battery_main   std_msgs/Float32   main battery V, 1 Hz
    subscribe /teensy/led            std_msgs/Bool      onboard LED

  The LED is the only actuator that exists yet. It proves the subscribe path
  end to end without touching a single robot peripheral.

  ---------------------------------------------------------------------------
  RECONNECTION
  ---------------------------------------------------------------------------
  A naive micro-ROS sketch hangs forever if the agent is not up at boot, and
  stays dead if the agent restarts. On a robot both happen routinely — the
  Jetson reboots, the agent gets restarted. So this runs a connection state
  machine that pings for the agent, builds its entities when one appears, and
  tears them down cleanly when it vanishes. The console keeps working in every
  state, which is the whole point of Dual Serial.
*/

#include <micro_ros_arduino.h>

#include <stdio.h>
#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>

#include <std_msgs/msg/int32.h>
#include <std_msgs/msg/float32.h>
#include <std_msgs/msg/bool.h>

#include <Servo.h>  // Neck pan/tilt servos (SG90)

// ---------------------------------------------------------------------------
// Transport override: move micro-ROS from Serial to SerialUSB1.
// These are strong definitions of the library's weak symbols.
// ---------------------------------------------------------------------------
extern "C" {

bool arduino_transport_open(struct uxrCustomTransport * transport) {
  (void)transport;
  SerialUSB1.begin(115200);
  return true;
}

bool arduino_transport_close(struct uxrCustomTransport * transport) {
  (void)transport;
  SerialUSB1.end();
  return true;
}

// NOTE: micro_ros_arduino.h declares buf as `const uint8_t *` while
// default_transport.cpp defines it non-const. The header wins here, since we
// include it — C linkage means the symbol still overrides the weak definition.
size_t arduino_transport_write(struct uxrCustomTransport * transport,
                               const uint8_t * buf, size_t len, uint8_t * errcode) {
  (void)transport; (void)errcode;
  return SerialUSB1.write(buf, len);
}

size_t arduino_transport_read(struct uxrCustomTransport * transport,
                              uint8_t * buf, size_t len, int timeout,
                              uint8_t * errcode) {
  (void)transport; (void)errcode;
  SerialUSB1.setTimeout(timeout);
  return SerialUSB1.readBytes((char *)buf, len);
}

}  // extern "C"

// ---------------------------------------------------------------------------

const char *FW_VERSION = "microros-0.4.0";
const int LED_PIN = 13;
const uint32_t HEARTBEAT_MS = 1000;

// --- Main battery voltage sensor (A0) ---
// Voltage Sensor Module Max 25V: 30k/7.5k divider = factor 5.
// 3S Li-ion pack: 12.6V max → 2.52V on A0 (safe for 3.3V ADC).
const int BATTERY_MAIN_PIN = A0;
const float BATTERY_DIVIDER = 5.0;
const float ADC_REF = 3.3;
const int ADC_MAX = 4095;  // 12-bit

// Cached readings (updated every heartbeat, published when agent is up).
float batteryMainV = 0.0;
int   batteryMainRaw = 0;

// --- COB LED strip via D4184 MOSFET module (pin 4) ---
// Low-side switch: the strip sits across OUT+/OUT- and the module chops OUT-
// against VIN-. 18 kHz is inside the module's 0-20 kHz spec, above adult
// hearing so the strip does not whine, and far above any camera shutter so it
// cannot band the OV9281s or the Brio.
const int LED_STRIP_PIN = 4;
const int STRIP_PWM_HZ  = 18000;
const int STRIP_MAX     = 4095;   // 12-bit, matches analogWriteResolution

// Brightness ceiling. Held at ~39% while the strip shared the LM2596S 5V rail
// with the neck servos — at full brightness it sagged the pack ~200 mV and made
// the servos strain. Lifted to full 2026-08-26 once the strip moved onto its own
// MINI560 (5A) fed from the 12.6V pack. Drop it again if the strip is ever put
// back on a shared rail.
const int STRIP_DUTY_MAX = STRIP_MAX;

// --- Ambient light sensor (Keyestudio photoresistor module, A1) ---
// The 10k half of the divider is on the module; S is its midpoint. Powered
// from 3.3V, so S can never exceed the ADC limit.
const int LDR_PIN = A1;

// Which way the module's divider is wired — batches differ. true = a lit
// sensor reads high. Flip this if covering the sensor makes the strip go
// DARKER instead of brighter.
const bool LDR_BRIGHT_IS_HIGH = true;

// Raw ADC values bracketing the useful range; readings outside clamp. Tune
// with the CAL console commands, then paste the results back here — they are
// not persisted across a reboot or a reflash.
//
// Measured 2026-08-26 with the Keyestudio module on A1:
//   529  — sensor covered by a hand
//   3163 — full daylight
//   ~950-1270 — normally lit room at night
//
// The bright endpoint is deliberately NOT the 3163 daylight figure. Against
// that ceiling a lit evening room maps to ~78% brightness and the strip would
// run near-full every night. 1400 means "the room is adequately lit, strip
// off", and anything brighter simply clamps. Raise it to make the strip more
// eager, lower it to make it lazier.
int ldrRawDark   = 529;
int ldrRawBright = 1400;

// Slow enough that the strip lighting its own sensor cannot start an
// oscillation. At 20 Hz updates this is roughly a one-second time constant.
const float STRIP_SMOOTH = 0.05f;
const uint32_t STRIP_UPDATE_MS = 50;

int   ldrRaw        = 0;
float ldrNormalized = 0.0;   // 0 = dark room, 1 = bright room
float stripSmoothed = 0.0;   // 0..1, before gamma
int   stripDuty     = 0;     // last value written to the pin
float stripManual   = -1.0;  // <0 = follow the sensor, 0..1 = forced level
uint32_t lastStripUpdate = 0;

// --- Neck pan/tilt servos (SG90, 5V from LM2596S) ---
Servo servoPan;
Servo servoTilt;
const int SERVO_PAN_PIN = 2;
const int SERVO_TILT_PIN = 3;
int servoPanPos = 90;   // 0-180 degrees, 90 = center
int servoTiltPos = 90;
const int SERVO_PAN_MIN = 70;   // pan limits
const int SERVO_PAN_MAX = 140;
const int SERVO_TILT_MIN = 60;  // tilt limits
const int SERVO_TILT_MAX = 120;

// Smooth motion: ease into target position instead of jumping
float servoPanCurrent = 90.0;
float servoTiltCurrent = 90.0;
const float SERVO_SMOOTH = 0.03;  // 3% of remaining distance per loop iteration
int lastPanWritten = 90;
int lastTiltWritten = 90;

// How often to look for an agent while disconnected. Cheap ping, so half a
// second keeps reconnection prompt without flooding the link.
const uint32_t AGENT_PING_MS = 500;

rcl_allocator_t   allocator;
rclc_support_t    support;
rcl_node_t        node;
rclc_executor_t   executor;

rcl_publisher_t   pub_heartbeat;
rcl_publisher_t   pub_temperature;
rcl_publisher_t   pub_battery_main;
rcl_publisher_t   pub_light;
rcl_subscription_t sub_led;
rcl_subscription_t sub_strip;

std_msgs__msg__Int32   msg_heartbeat;
std_msgs__msg__Float32 msg_temperature;
std_msgs__msg__Float32 msg_battery_main;
std_msgs__msg__Float32 msg_light;
std_msgs__msg__Bool    msg_led;
std_msgs__msg__Float32 msg_strip;

enum AgentState { WAITING_AGENT, AGENT_AVAILABLE, AGENT_CONNECTED, AGENT_DISCONNECTED };
AgentState agentState = WAITING_AGENT;

uint32_t bootMillis = 0;
uint32_t lastHeartbeat = 0;
uint32_t lastAgentPing = 0;
uint32_t heartbeatSeq = 0;
uint32_t loopCount = 0;
uint32_t loopsPerSec = 0;
uint32_t lastRateCalc = 0;
uint32_t agentConnects = 0;
uint32_t agentDrops = 0;
bool ledState = false;

char cmdBuf[128];
uint8_t cmdLen = 0;

// Run fn; on failure return false from the calling function. Used during
// entity creation so a partial build is reported rather than half-committed.
#define RCCHECK(fn) { rcl_ret_t rc = fn; if (rc != RCL_RET_OK) return false; }
// Fire and forget — a failed publish is reported via the console, not fatal.
#define RCSOFT(fn)  { rcl_ret_t rc = fn; (void)rc; }

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

const char *agentStateName() {
  switch (agentState) {
    case WAITING_AGENT:      return "waiting";
    case AGENT_AVAILABLE:    return "available";
    case AGENT_CONNECTED:    return "connected";
    case AGENT_DISCONNECTED: return "disconnected";
  }
  return "?";
}

void led_callback(const void *msgin) {
  const std_msgs__msg__Bool *m = (const std_msgs__msg__Bool *)msgin;
  ledState = m->data;
  digitalWrite(LED_PIN, ledState ? HIGH : LOW);
  Serial.print("EVENT led=");
  Serial.println(ledState ? "on" : "off");
}

// Perceived brightness tracks roughly the square of duty cycle, so a linear
// ramp looks wrong at the bottom end. Gamma 2.0 is cheap and close enough.
static inline int stripGamma(float level) {
  return (int)(level * level * STRIP_MAX + 0.5);
}

void updateStrip() {
  ldrRaw = analogRead(LDR_PIN);

  int lo = min(ldrRawDark, ldrRawBright);
  int hi = max(ldrRawDark, ldrRawBright);
  float span = (float)(hi - lo);
  float n = (span > 1.0) ? ((float)constrain(ldrRaw, lo, hi) - lo) / span : 0.0;
  ldrNormalized = LDR_BRIGHT_IS_HIGH ? n : (1.0 - n);

  // Darker room -> brighter strip, unless a manual level is in force.
  float target = (stripManual >= 0.0) ? stripManual : (1.0 - ldrNormalized);

  stripSmoothed += (target - stripSmoothed) * STRIP_SMOOTH;
  int duty = stripGamma(constrain(stripSmoothed, 0.0, 1.0));
  duty = min(duty, STRIP_DUTY_MAX);
  if (duty != stripDuty) {
    stripDuty = duty;
    analogWrite(LED_STRIP_PIN, stripDuty);
  }
}

void strip_callback(const void *msgin) {
  const std_msgs__msg__Float32 *m = (const std_msgs__msg__Float32 *)msgin;
  // Negative hands control back to the light sensor.
  stripManual = (m->data < 0.0) ? -1.0 : constrain(m->data, 0.0, 1.0);
  Serial.print("EVENT strip=");
  if (stripManual < 0.0) Serial.println("auto");
  else                   Serial.println(stripManual, 2);
}

bool createEntities() {
  allocator = rcl_get_default_allocator();
  RCCHECK(rclc_support_init(&support, 0, NULL, &allocator));
  RCCHECK(rclc_node_init_default(&node, "teensy_node", "", &support));

  RCCHECK(rclc_publisher_init_default(
      &pub_heartbeat, &node,
      ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32), "teensy/heartbeat"));

  RCCHECK(rclc_publisher_init_default(
      &pub_temperature, &node,
      ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32), "teensy/temperature"));

  RCCHECK(rclc_publisher_init_default(
      &pub_battery_main, &node,
      ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32), "teensy/battery_main"));

  RCCHECK(rclc_publisher_init_default(
      &pub_light, &node,
      ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32), "teensy/light_level"));

  RCCHECK(rclc_subscription_init_default(
      &sub_led, &node,
      ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Bool), "teensy/led"));

  RCCHECK(rclc_subscription_init_default(
      &sub_strip, &node,
      ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32), "teensy/led_strip"));

  // Handle count must match the number of subscriptions added below.
  executor = rclc_executor_get_zero_initialized_executor();
  RCCHECK(rclc_executor_init(&executor, &support.context, 2, &allocator));
  RCCHECK(rclc_executor_add_subscription(
      &executor, &sub_led, &msg_led, &led_callback, ON_NEW_DATA));
  RCCHECK(rclc_executor_add_subscription(
      &executor, &sub_strip, &msg_strip, &strip_callback, ON_NEW_DATA));

  return true;
}

void destroyEntities() {
  // Stop the session from blocking on a dead link during teardown.
  rmw_context_t *rmw_context = rcl_context_get_rmw_context(&support.context);
  (void)rmw_uros_set_context_entity_destroy_session_timeout(rmw_context, 0);

  rcl_publisher_fini(&pub_heartbeat, &node);
  rcl_publisher_fini(&pub_temperature, &node);
  rcl_publisher_fini(&pub_battery_main, &node);
  rcl_publisher_fini(&pub_light, &node);
  rcl_subscription_fini(&sub_led, &node);
  rcl_subscription_fini(&sub_strip, &node);
  rclc_executor_fini(&executor);
  rcl_node_fini(&node);
  rclc_support_fini(&support);
}

// ---------------------------------------------------------------------------
// Console — same protocol as teensy_bringup so health_check.py still works,
// plus micro-ROS specific fields.
// ---------------------------------------------------------------------------

void sendInfo() {
  Serial.print("INFO fw=");           Serial.print(FW_VERSION);
  Serial.print(" board=teensy41 mcu=imxrt1062");
  Serial.print(" cpu_hz=");           Serial.print(F_CPU_ACTUAL);
  Serial.print(" serial=");           Serial.print(HW_OCOTP_MAC0 & 0xFFFFFF);
  Serial.print(" usb=serial");        // Dual Serial: this is CDC #1
  Serial.print(" transport=SerialUSB1");
  Serial.print(" built=" __DATE__ " " __TIME__);
  Serial.println();
}

void sendHealth() {
  Serial.print("HEALTH temp_c=");     Serial.print(tempmonGetTemp(), 1);
  Serial.print(" uptime_ms=");        Serial.print(millis() - bootMillis);
  Serial.print(" loop_hz=");          Serial.print(loopsPerSec);
  Serial.print(" restart=");          Serial.print(restartCause());
  Serial.print(" heartbeats=");       Serial.print(heartbeatSeq);
  Serial.println();
}

void sendRos() {
  Serial.print("ROS agent=");         Serial.print(agentStateName());
  Serial.print(" connects=");         Serial.print(agentConnects);
  Serial.print(" drops=");            Serial.print(agentDrops);
  Serial.print(" led=");              Serial.print(ledState ? "on" : "off");
  Serial.println();
}

void sendBattery() {
  Serial.print("BATTERY main_v=");    Serial.print(batteryMainV, 3);
  Serial.print(" raw=");              Serial.print(batteryMainRaw);
  Serial.print(" pin_v=");            Serial.print((float)batteryMainRaw * ADC_REF / ADC_MAX, 3);
  Serial.println();
}

void sendLight() {
  Serial.print("LIGHT raw=");      Serial.print(ldrRaw);
  Serial.print(" norm=");          Serial.print(ldrNormalized, 3);
  Serial.print(" cal_dark=");      Serial.print(ldrRawDark);
  Serial.print(" cal_bright=");    Serial.print(ldrRawBright);
  Serial.print(" duty=");          Serial.print(stripDuty);
  Serial.print("/");               Serial.print(STRIP_DUTY_MAX);
  Serial.print(" (cap of ");       Serial.print(STRIP_MAX);  Serial.print(")");
  Serial.print(" mode=");          Serial.print(stripManual >= 0.0 ? "manual" : "auto");
  Serial.println();
}

void handleCommand(char *cmd) {
  size_t n = strlen(cmd);
  while (n > 0 && (cmd[n - 1] == '\r' || cmd[n - 1] == ' ')) cmd[--n] = '\0';
  if (n == 0) return;

  if (strcmp(cmd, "PING") == 0) {
    Serial.print("PONG ");  Serial.println(millis());
  } else if (strcmp(cmd, "INFO") == 0) {
    sendInfo();
  } else if (strcmp(cmd, "HEALTH") == 0) {
    sendHealth();
  } else if (strcmp(cmd, "ROS") == 0) {
    sendRos();
  } else if (strcmp(cmd, "BATTERY") == 0) {
    sendBattery();
  } else if (strcmp(cmd, "LIGHT") == 0) {
    sendLight();
  } else if (strcmp(cmd, "CAL dark") == 0) {
    // Cover the sensor, then send this.
    ldrRawDark = analogRead(LDR_PIN);
    Serial.print("CAL dark=");    Serial.println(ldrRawDark);
  } else if (strcmp(cmd, "CAL bright") == 0) {
    // Shine a torch on the sensor, then send this.
    ldrRawBright = analogRead(LDR_PIN);
    Serial.print("CAL bright=");  Serial.println(ldrRawBright);
  } else if (strcmp(cmd, "STRIP") == 0) {
    Serial.println("STRIP usage: STRIP auto | STRIP 0-100");
    sendLight();
  } else if (strncmp(cmd, "STRIP ", 6) == 0) {
    char *p = cmd + 6;
    while (*p == ' ') p++;
    if (strcmp(p, "auto") == 0) {
      stripManual = -1.0;
      Serial.println("STRIP mode=auto");
    } else {
      stripManual = constrain(atoi(p), 0, 100) / 100.0;
      Serial.print("STRIP mode=manual level=");  Serial.println(stripManual, 2);
    }
  } else if (strcmp(cmd, "SERVO") == 0) {
    Serial.println("SERVO usage: SERVO pan=90 tilt=90  (0-180)");
    Serial.print("SERVO current pan="); Serial.print(servoPanPos);
    Serial.print(" tilt="); Serial.println(servoTiltPos);
  } else if (strncmp(cmd, "SERVO ", 6) == 0) {
    // Parse: SERVO pan=90 tilt=80
    char *p = cmd + 6;
    while (*p) {
      if (strncmp(p, "pan=", 4) == 0) {
        servoPanPos = constrain(atoi(p + 4), SERVO_PAN_MIN, SERVO_PAN_MAX);
      } else if (strncmp(p, "tilt=", 5) == 0) {
        servoTiltPos = constrain(atoi(p + 5), SERVO_TILT_MIN, SERVO_TILT_MAX);
      }
      while (*p && *p != ' ') p++;
      while (*p == ' ') p++;
    }
    Serial.print("SERVO set pan="); Serial.print(servoPanPos);
    Serial.print(" tilt="); Serial.println(servoTiltPos);
    } else {
    Serial.print("ERR unknown_command ");  Serial.println(cmd);
  }
}

void pollConsole() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      cmdBuf[cmdLen] = '\0';
      handleCommand(cmdBuf);
      cmdLen = 0;
    } else if (cmdLen < sizeof(cmdBuf) - 1) {
      cmdBuf[cmdLen++] = c;
    } else {
      cmdLen = 0;
      Serial.println("ERR line_too_long");
    }
  }
}

// ---------------------------------------------------------------------------

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);
  // No `while (!Serial)`. Headless robot: blocking on a host that may never
  // open the console would stop the ROS side coming up at all.

  analogReadResolution(12);    // use full 12-bit ADC (default is 10-bit)
  analogReadAveraging(8);      // average 8 samples for noise reduction

  // LED strip. analogWriteResolution is global to analogWrite; the Servo
  // library does not use it, so the neck servos are unaffected.
  analogWriteResolution(12);
  analogWriteFrequency(LED_STRIP_PIN, STRIP_PWM_HZ);
  pinMode(LED_STRIP_PIN, OUTPUT);
  analogWrite(LED_STRIP_PIN, 0);

  // Neck servos
  servoPan.attach(SERVO_PAN_PIN);
  servoTilt.attach(SERVO_TILT_PIN);
  servoPanCurrent = servoPanPos;
  servoTiltCurrent = servoTiltPos;

  set_microros_transports();   // uses our SerialUSB1 overrides

  bootMillis    = millis();
  lastRateCalc  = bootMillis;
  lastHeartbeat = bootMillis;

  Serial.println();
  Serial.println("BOOT teensy41 microros");
  sendInfo();
}

void loop() {
  loopCount++;

  // --- Smooth servo motion (eases toward target) ---
  servoPanCurrent += (servoPanPos - servoPanCurrent) * SERVO_SMOOTH;
  servoTiltCurrent += (servoTiltPos - servoTiltCurrent) * SERVO_SMOOTH;
  int newPan = (int)(servoPanCurrent + 0.5);
  int newTilt = (int)(servoTiltCurrent + 0.5);
  if (newPan != lastPanWritten) {
    servoPan.write(newPan);
    lastPanWritten = newPan;
  }
  if (newTilt != lastTiltWritten) {
    servoTilt.write(SERVO_TILT_MAX + SERVO_TILT_MIN - newTilt);  // reversed mount
    lastTiltWritten = newTilt;
  }
  pollConsole();          // always works, in every agent state

  uint32_t now = millis();

  // Ambient-light tracking runs at 20 Hz — fast enough to look smooth, slow
  // enough to stay cheap next to the servo easing.
  if (now - lastStripUpdate >= STRIP_UPDATE_MS) {
    lastStripUpdate = now;
    updateStrip();
  }

  if (now - lastRateCalc >= 1000) {
    loopsPerSec = loopCount;
    loopCount = 0;
    lastRateCalc = now;
  }

  switch (agentState) {
    case WAITING_AGENT:
      if (now - lastAgentPing >= AGENT_PING_MS) {
        lastAgentPing = now;
        agentState = (rmw_uros_ping_agent(100, 1) == RMW_RET_OK)
                     ? AGENT_AVAILABLE : WAITING_AGENT;
      }
      break;

    case AGENT_AVAILABLE:
      if (createEntities()) {
        agentState = AGENT_CONNECTED;
        agentConnects++;
        Serial.println("EVENT agent=connected");
      } else {
        destroyEntities();
        agentState = WAITING_AGENT;
        Serial.println("EVENT agent=create_failed");
      }
      break;

    case AGENT_CONNECTED:
      if (now - lastAgentPing >= AGENT_PING_MS * 4) {
        lastAgentPing = now;
        if (rmw_uros_ping_agent(200, 1) != RMW_RET_OK) {
          agentState = AGENT_DISCONNECTED;
          break;
        }
      }
      rclc_executor_spin_some(&executor, RCL_MS_TO_NS(1));
      break;

    case AGENT_DISCONNECTED:
      destroyEntities();
      agentDrops++;
      agentState = WAITING_AGENT;
      Serial.println("EVENT agent=disconnected");
      break;
  }

  if (now - lastHeartbeat >= HEARTBEAT_MS) {
    lastHeartbeat = now;
    heartbeatSeq++;

    // The LED is owned by the ROS subscriber once connected; only blink it as
    // a liveness indicator while there is no agent to drive it.
    if (agentState != AGENT_CONNECTED) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    }

    // Read main battery voltage (every heartbeat, regardless of agent state).
    batteryMainRaw = analogRead(BATTERY_MAIN_PIN);
    float pinV = (float)batteryMainRaw * ADC_REF / ADC_MAX;
    batteryMainV = pinV * BATTERY_DIVIDER;

    if (agentState == AGENT_CONNECTED) {
      msg_heartbeat.data     = (int32_t)heartbeatSeq;
      msg_temperature.data   = tempmonGetTemp();
      msg_battery_main.data  = batteryMainV;
      msg_light.data         = ldrNormalized;
      RCSOFT(rcl_publish(&pub_heartbeat, &msg_heartbeat, NULL));
      RCSOFT(rcl_publish(&pub_temperature, &msg_temperature, NULL));
      RCSOFT(rcl_publish(&pub_battery_main, &msg_battery_main, NULL));
      RCSOFT(rcl_publish(&pub_light, &msg_light, NULL));
    }

    Serial.print("HEARTBEAT seq=");  Serial.print(heartbeatSeq);
    Serial.print(" uptime_ms=");     Serial.print(now - bootMillis);
    Serial.print(" temp_c=");        Serial.print(tempmonGetTemp(), 1);
    Serial.print(" loop_hz=");       Serial.print(loopsPerSec);
    Serial.print(" agent=");         Serial.print(agentStateName());
    Serial.print(" bat_v=");         Serial.print(batteryMainV, 2);
    Serial.print(" ldr=");           Serial.print(ldrRaw);
    Serial.print(" strip=");         Serial.print(stripDuty);
    Serial.println();
  }
}
