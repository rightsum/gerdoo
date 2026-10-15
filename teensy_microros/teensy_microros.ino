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

#include "arm_types.h"
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
// Straight ahead on this bracket, found by adjustment — not the midpoint of
// the servo range, because the gimbal is not mounted symmetrically.
int servoPanPos = 110;
int servoTiltPos = 110;
const int SERVO_PAN_MIN = 70;   // pan limits
const int SERVO_PAN_MAX = 140;
const int SERVO_TILT_MIN = 60;  // tilt limits
const int SERVO_TILT_MAX = 120;

// The tilt servo is mounted reversed, so a larger logical angle means a
// smaller pulse. Wrapped in a function because this has to be applied
// identically at boot and in the loop; two copies of it would drift.
static inline void writeTilt(int logical) {
  servoTilt.write(SERVO_TILT_MAX + SERVO_TILT_MIN - logical);
}

// Smooth motion.
//
// This used to ease by a fixed FRACTION per loop iteration, which sounds gentle
// until you notice the loop runs at ~999 Hz: 3% of the remaining distance a
// thousand times a second is a peak of roughly 1200 deg/s. A human neck manages
// 100-200. It looked and sounded like a machine snapping to position.
//
// Now it is time-based and speed-limited, updating at 50 Hz because that is the
// rate an SG90 actually samples its input — writing faster is churn the servo
// cannot see.
const uint32_t SERVO_UPDATE_MS = 20;      // 50 Hz, the servo's own PWM rate
const float SERVO_MAX_DPS = 70.0;         // top speed, degrees per second
const float SERVO_EASE_TAU = 0.18;        // seconds; softens the last few degrees

// Holding position is what makes an SG90 buzz. Pan carries no weight against
// gravity, so once it has settled it can be released and go quiet. Tilt holds
// the screen up and must stay energised or the head drops.
const uint32_t PAN_IDLE_DETACH_MS = 1500;

uint32_t lastServoUpdate = 0;
uint32_t panSettledAt = 0;
bool panAttached = true;

float servoPanCurrent = 110.0;
float servoTiltCurrent = 110.0;

// Move `current` toward `target` for one tick: an exponential ease so it settles
// softly, capped by a top speed so a large jump does not start out violently.
static inline float easeToward(float current, float target, float dt) {
  float delta = target - current;
  if (fabsf(delta) < 0.05f) return (float)target;
  float step = delta * (dt / SERVO_EASE_TAU);
  float cap = SERVO_MAX_DPS * dt;
  if (step > cap) step = cap;
  if (step < -cap) step = -cap;
  return current + step;
}
int lastPanWritten = 110;
int lastTiltWritten = 110;

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

// ---------------------------------------------------------------------------
// Arm servo bus — Feetech STS3215 through the Waveshare driver board
// ---------------------------------------------------------------------------
// READ-ONLY. BUS SCAN sends PING (0x01) and READ (0x02) packets and nothing
// else: no WRITE, no SYNC_WRITE, no torque enable, no RESET. A servo answers
// a ping or a read without moving.
//
// Wiring: Teensy SerialN TX/RX to the board's UART header, board jumper on A
// (UART mode), grounds common. The board turns the two-wire UART into the
// servos' one-wire bus. The port is opened on the first scan, not at boot, so
// nothing drives its pins until asked to. Serial3 is not offered: its RX is
// pin 15, the light sensor.

const uint32_t BUS_BAUD = 1000000;           // ElRobot / Feetech factory default
const uint8_t  STS_PING = 0x01, STS_READ = 0x02;
const uint8_t  STS_REG_MODEL = 3;            // u16
const uint8_t  STS_REG_TORQUE_ENABLE = 40;   // u8
const uint8_t  STS_REG_PRESENT = 56;         // position u16, speed u16, load u16, volt u8 (0.1 V), temp u8
const uint32_t BUS_REPLY_US = 2000;
bool busOpened[9] = {false};
uint32_t busRxBytes = 0;     // every byte seen during a scan, echoes included

HardwareSerial *busPort(int n) {
  switch (n) {
    case 1: return &Serial1;
    case 2: return &Serial2;
    case 7: return &Serial7;
    case 8: return &Serial8;
  }
  return nullptr;
}

// Find a valid status packet from `id` in buf. The board's one-wire bus can
// echo our own request back on RX, so an exact copy of it at the start is
// skipped. Returns the parameter count, -1 if nothing valid yet, and sets
// *garbled when bytes arrived that do not form a valid reply — what two
// servos with the same ID answering at once looks like.
int busParse(const uint8_t *buf, uint8_t n, const uint8_t *req, uint8_t reqLen, uint8_t id,
             uint8_t *out, uint8_t outMax, uint8_t *err, bool *garbled) {
  uint8_t i = (n >= reqLen && memcmp(buf, req, reqLen) == 0) ? reqLen : 0;
  *garbled = n > i;
  for (; i + 4 <= n; i++) {
    if (buf[i] != 0xFF || buf[i + 1] != 0xFF || buf[i + 2] != id) continue;
    uint8_t len = buf[i + 3];
    if (len < 2 || i + 4 + len > n) return -1;
    uint8_t sum = 0;
    for (uint8_t k = i + 2; k <= i + 2 + len; k++) sum += buf[k];
    if ((uint8_t)~sum != buf[i + 3 + len]) continue;
    *err = buf[i + 4];
    uint8_t m = min((uint8_t)(len - 2), outMax);
    memcpy(out, buf + i + 5, m);
    *garbled = false;
    return m;
  }
  return -1;
}

// One request and its reply. Returns the reply's parameter count, or -1.
int busTransact(HardwareSerial &s, uint8_t id, uint8_t instr, const uint8_t *params, uint8_t np,
                uint8_t *out, uint8_t outMax, uint8_t *err, bool *garbled) {
  uint8_t req[16];          // header 5 + up to 10 params + checksum
  uint8_t len = np + 2, sum = id + len + instr;
  req[0] = 0xFF; req[1] = 0xFF; req[2] = id; req[3] = len; req[4] = instr;
  for (uint8_t i = 0; i < np; i++) { req[5 + i] = params[i]; sum += params[i]; }
  req[5 + np] = ~sum;
  uint8_t reqLen = 6 + np;

  while (s.available()) s.read();
  s.write(req, reqLen);
  s.flush();

  uint8_t buf[64];
  uint8_t n = 0;
  int got = -1;
  *garbled = false;
  elapsedMicros t;
  while (t < BUS_REPLY_US && n < sizeof(buf)) {
    if (!s.available()) continue;
    buf[n++] = s.read();
    busRxBytes++;
    got = busParse(buf, n, req, reqLen, id, out, outMax, err, garbled);
    if (got >= 0) return got;
  }
  if (n > 0) busParse(buf, n, req, reqLen, id, out, outMax, err, garbled);
  return got;
}

void busScan(int portNum) {
  HardwareSerial *s = busPort(portNum);
  if (!s) {
    Serial.println("ERR bus_port (use 1, 2, 7 or 8)");
    return;
  }
  if (!busOpened[portNum]) {
    s->begin(BUS_BAUD);
    busOpened[portNum] = true;
  }
  Serial.print("BUS SCAN port=Serial");  Serial.print(portNum);
  Serial.print(" baud=");                Serial.print(BUS_BAUD);
  Serial.println(" (ping + read only)");

  uint8_t found[253], nFound = 0;
  busRxBytes = 0;
  uint8_t out[8], err;
  bool garbled;
  for (int id = 0; id <= 252; id++) {
    if (busTransact(*s, id, STS_PING, nullptr, 0, out, sizeof(out), &err, &garbled) >= 0) {
      found[nFound++] = id;
    } else if (garbled) {
      Serial.print("BUS id=");  Serial.print(id);
      Serial.println(" garbled reply (two servos sharing this ID?)");
    }
  }

  for (uint8_t k = 0; k < nFound; k++) {
    uint8_t id = found[k];
    uint8_t model[2] = {0, 0}, torque[1] = {0}, present[8] = {0};
    const uint8_t qModel[2] = {STS_REG_MODEL, 2};
    const uint8_t qTorque[2] = {STS_REG_TORQUE_ENABLE, 1};
    const uint8_t qPresent[2] = {STS_REG_PRESENT, 8};
    bool okModel = busTransact(*s, id, STS_READ, qModel, 2, model, 2, &err, &garbled) == 2;
    bool okTorque = busTransact(*s, id, STS_READ, qTorque, 2, torque, 1, &err, &garbled) == 1;
    bool okPresent = busTransact(*s, id, STS_READ, qPresent, 2, present, 8, &err, &garbled) == 8;
    Serial.print("BUS id=");  Serial.print(id);
    if (okModel) { Serial.print(" model=");  Serial.print(model[0] | (model[1] << 8)); }
    if (okPresent) {
      Serial.print(" pos=");    Serial.print(present[0] | (present[1] << 8));
      Serial.print(" volt=");   Serial.print(present[6] / 10.0, 1);
      Serial.print(" temp=");   Serial.print(present[7]);
    }
    if (okTorque) { Serial.print(" torque=");  Serial.print(torque[0]); }
    Serial.print(" err=0x");  Serial.println(err, HEX);
  }

  // rx_bytes=0 means nothing reached RX at all: wiring, jumper or power,
  // not the servos.
  Serial.print("BUS SCAN done rx_bytes=");  Serial.print(busRxBytes);
  Serial.print(" found=");  Serial.print(nFound);
  Serial.print(" ids=");
  for (uint8_t k = 0; k < nFound; k++) {
    if (k) Serial.print(",");
    Serial.print(found[k]);
  }
  Serial.println();
}

// Debug: one READ to one ID, then every byte that comes back, raw. Read-only.
void busReadRaw(int portNum, int id, int addr, int len) {
  HardwareSerial *s = busPort(portNum);
  if (!s || id < 0 || id > 252 || addr < 0 || addr > 255 || len < 1 || len > 32) {
    Serial.println("ERR usage: BUS READ <id> <addr> <len>  (port 7)");
    return;
  }
  if (!busOpened[portNum]) {
    s->begin(BUS_BAUD);
    busOpened[portNum] = true;
  }
  uint8_t req[8] = {0xFF, 0xFF, (uint8_t)id, 4, STS_READ, (uint8_t)addr, (uint8_t)len, 0};
  req[7] = ~(uint8_t)(req[2] + req[3] + req[4] + req[5] + req[6]);
  while (s->available()) s->read();
  s->write(req, 8);
  s->flush();
  uint8_t buf[64];
  uint8_t n = 0;
  elapsedMicros t;
  while (t < 5000 && n < sizeof(buf)) {
    if (s->available()) buf[n++] = s->read();
  }
  Serial.print("BUS RAW id=");  Serial.print(id);
  Serial.print(" addr=");       Serial.print(addr);
  Serial.print(" len=");        Serial.print(len);
  Serial.print(" got=");        Serial.print(n);
  Serial.print(" :");
  for (uint8_t i = 0; i < n; i++) {
    Serial.print(buf[i] < 16 ? " 0" : " ");
    Serial.print(buf[i], HEX);
  }
  Serial.println();
}

// Change one servo's ID. The only write in this file. It touches the EEPROM
// lock (55) and the ID register (5) and nothing else, so torque stays off and
// nothing moves. Refuses unless exactly one servo answers at `from` (five
// clean position reads in a row; two servos with one ID garble their replies)
// and nothing answers at `to`.
const uint8_t STS_WRITE = 0x03, STS_REG_ID = 5, STS_REG_LOCK = 55;

bool busOnlyOne(HardwareSerial &s, uint8_t id) {
  const uint8_t q[2] = {STS_REG_PRESENT, 2};
  uint8_t out[2], err;
  bool garbled;
  for (int i = 0; i < 5; i++) {
    if (busTransact(s, id, STS_READ, q, 2, out, 2, &err, &garbled) != 2) return false;
  }
  return true;
}

void busSetId(int portNum, int from, int to) {
  HardwareSerial *s = busPort(portNum);
  if (!s || from < 0 || from > 252 || to < 1 || to > 252 || from == to) {
    Serial.println("ERR usage: BUS SETID <from> <to>  (to = 1..252, port 7)");
    return;
  }
  if (!busOpened[portNum]) {
    s->begin(BUS_BAUD);
    busOpened[portNum] = true;
  }
  uint8_t out[2], err;
  bool garbled;
  if (busTransact(*s, to, STS_PING, nullptr, 0, out, 2, &err, &garbled) >= 0 || garbled) {
    Serial.print("BUS SETID refused: something already answers at id=");  Serial.println(to);
    return;
  }
  if (!busOnlyOne(*s, from)) {
    Serial.print("BUS SETID refused: id=");  Serial.print(from);
    Serial.println(" is missing or shared by more than one servo; isolate one servo first");
    return;
  }
  const uint8_t unlock[2] = {STS_REG_LOCK, 0};
  const uint8_t setId[2] = {STS_REG_ID, (uint8_t)to};
  const uint8_t lock[2] = {STS_REG_LOCK, 1};
  busTransact(*s, from, STS_WRITE, unlock, 2, out, 2, &err, &garbled);
  busTransact(*s, from, STS_WRITE, setId, 2, out, 2, &err, &garbled);
  delay(20);
  busTransact(*s, to, STS_WRITE, lock, 2, out, 2, &err, &garbled);
  delay(20);

  const uint8_t qId[2] = {STS_REG_ID, 1};
  uint8_t idNow[1] = {0};
  bool ok = busTransact(*s, to, STS_READ, qId, 2, idNow, 1, &err, &garbled) == 1 && idNow[0] == to;
  bool oldGone = busTransact(*s, from, STS_PING, nullptr, 0, out, 2, &err, &garbled) < 0 && !garbled;
  Serial.print(ok && oldGone ? "BUS SETID ok " : "BUS SETID FAILED ");
  Serial.print(from);  Serial.print(" -> ");  Serial.print(to);
  Serial.print(" (reads back id=");  Serial.print(idNow[0]);
  Serial.print(", old id ");  Serial.print(oldGone ? "silent" : "STILL ANSWERS");
  Serial.println(")");
}

// ---------------------------------------------------------------------------
// Arms — position control for the control panel
// ---------------------------------------------------------------------------
// Two ElRobot followers on one bus: L = IDs 1..8, R = IDs 11..18, base to
// gripper. Commands are "ARM <L|R> STATE | TORQUE ON | TORQUE OFF |
// SPEED <n> | MOVE <joint 1-8> <pos 0-4095>". Guard rails, all in place
// before any torque:
//   * MOVE is refused while that arm's torque is off.
//   * TORQUE ON sets each joint's goal to its present position BEFORE
//     enabling it, so switching on never makes a joint jump.
//   * Torque limit 300/1000 — ElRobot's own value while it explores a joint's
//     range — so a joint driven into a hard stop stalls instead of forcing it.
//   * Speed starts at 400 steps/s (about 35 deg/s), acceleration 50. SPEED
//     changes it (50-3000; the STS3215 tops out near 3000 steps/s, about
//     270 deg/s, at 12 V).
// TORQUE OFF releases all eight joints of that arm: the panel's emergency stop.

const uint8_t  ARM_PORT = 7, ARM_JOINTS = 8;
const uint8_t  STS_REG_ACC = 41, STS_REG_TORQUE_LIMIT = 48;   // goal block starts at ACC
const uint16_t ARM_TORQUE_LIMIT = 300;
const uint8_t  ARM_ACC = 50;

Arm arms[2] = {{'L', 1, false, 400}, {'R', 11, false, 400}};

Arm *armBySide(char c) {
  if (c == 'L') return &arms[0];
  if (c == 'R') return &arms[1];
  return nullptr;
}

HardwareSerial *armBus() {
  HardwareSerial *s = busPort(ARM_PORT);
  if (!busOpened[ARM_PORT]) {
    s->begin(BUS_BAUD);
    busOpened[ARM_PORT] = true;
  }
  return s;
}

bool busWrite(HardwareSerial &s, uint8_t id, const uint8_t *params, uint8_t np) {
  uint8_t out[2], err;
  bool garbled;
  return busTransact(s, id, STS_WRITE, params, np, out, 2, &err, &garbled) >= 0;
}

int armReadPos(HardwareSerial &s, uint8_t id) {
  const uint8_t q[2] = {STS_REG_PRESENT, 2};
  uint8_t out[2], err;
  bool garbled;
  if (busTransact(s, id, STS_READ, q, 2, out, 2, &err, &garbled) != 2) return -1;
  return out[0] | (out[1] << 8);
}

// Acceleration, goal position, goal time 0, goal speed — one write, as the
// Feetech SDK's WritePosEx does it.
bool armWriteGoal(HardwareSerial &s, uint8_t id, int pos, uint16_t speed) {
  pos = constrain(pos, 0, 4095);
  const uint8_t p[8] = {STS_REG_ACC, ARM_ACC, (uint8_t)(pos & 0xFF), (uint8_t)(pos >> 8),
                        0, 0, (uint8_t)(speed & 0xFF), (uint8_t)(speed >> 8)};
  return busWrite(s, id, p, 8);
}

bool armSetTorque(HardwareSerial &s, uint8_t id, bool on) {
  const uint8_t p[2] = {STS_REG_TORQUE_ENABLE, (uint8_t)(on ? 1 : 0)};
  return busWrite(s, id, p, 2);
}

void armState(Arm &a) {
  HardwareSerial &s = *armBus();
  int pos[ARM_JOINTS], load[ARM_JOINTS], temp[ARM_JOINTS];
  uint8_t torqued = 0;
  for (uint8_t j = 0; j < ARM_JOINTS; j++) {
    // Torque as the servos report it, not as this firmware remembers it: a
    // reboot or reflash forgets, while the servos keep holding.
    const uint8_t qt[2] = {STS_REG_TORQUE_ENABLE, 1};
    uint8_t te[1] = {0}, terr;
    bool tg;
    if (busTransact(s, a.firstId + j, STS_READ, qt, 2, te, 1, &terr, &tg) == 1 && te[0]) torqued++;
    const uint8_t q[2] = {STS_REG_PRESENT, 8};
    uint8_t out[8], err;
    bool garbled;
    if (busTransact(s, a.firstId + j, STS_READ, q, 2, out, 8, &err, &garbled) == 8) {
      pos[j] = out[0] | (out[1] << 8);
      load[j] = ((out[4] | (out[5] << 8)) & 0x3FF) / 10;   // magnitude, percent
      temp[j] = out[7];
    } else {
      pos[j] = load[j] = temp[j] = -1;
    }
  }
  a.torque = torqued == ARM_JOINTS;
  Serial.print("ARM ");  Serial.print(a.side);
  Serial.print(" STATE torque=");  Serial.print(a.torque ? 1 : 0);
  Serial.print(" speed=");         Serial.print(a.speed);
  const char *names[3] = {" pos=", " load=", " temp="};
  int *cols[3] = {pos, load, temp};
  for (uint8_t c = 0; c < 3; c++) {
    Serial.print(names[c]);
    for (uint8_t j = 0; j < ARM_JOINTS; j++) {
      if (j) Serial.print(",");
      Serial.print(cols[c][j]);
    }
  }
  Serial.println();
}

void armTorqueCmd(Arm &a, bool on) {
  HardwareSerial &s = *armBus();
  Serial.print("ARM ");  Serial.print(a.side);
  if (!on) {
    uint8_t ok = 0;
    for (uint8_t j = 0; j < ARM_JOINTS; j++) ok += armSetTorque(s, a.firstId + j, false);
    a.torque = false;
    Serial.print(" TORQUE off ok=");  Serial.println(ok);
    return;
  }
  // Every joint must answer before any of them gets torque.
  int pos[ARM_JOINTS];
  for (uint8_t j = 0; j < ARM_JOINTS; j++) {
    pos[j] = armReadPos(s, a.firstId + j);
    if (pos[j] < 0) {
      Serial.print(" TORQUE refused: id=");  Serial.print(a.firstId + j);
      Serial.println(" did not answer");
      return;
    }
  }
  const uint8_t lim[3] = {STS_REG_TORQUE_LIMIT, (uint8_t)(ARM_TORQUE_LIMIT & 0xFF),
                          (uint8_t)(ARM_TORQUE_LIMIT >> 8)};
  uint8_t ok = 0;
  for (uint8_t j = 0; j < ARM_JOINTS; j++) {
    uint8_t id = a.firstId + j;
    if (busWrite(s, id, lim, 3) && armWriteGoal(s, id, pos[j], a.speed) && armSetTorque(s, id, true)) ok++;
  }
  a.torque = true;
  Serial.print(" TORQUE on ok=");  Serial.println(ok);
}

void armMove(Arm &a, int joint, int pos) {
  Serial.print("ARM ");  Serial.print(a.side);
  if (!a.torque) {
    Serial.println(" MOVE refused: torque is off");
    return;
  }
  if (joint < 1 || joint > ARM_JOINTS || pos < 0 || pos > 4095) {
    Serial.println(" MOVE refused: usage MOVE <joint 1-8> <pos 0-4095>");
    return;
  }
  bool ok = armWriteGoal(*armBus(), a.firstId + joint - 1, pos, a.speed);
  Serial.print(" MOVE joint=");  Serial.print(joint);
  Serial.print(" goal=");        Serial.print(pos);
  Serial.println(ok ? " ok" : " failed");
}

void armCommand(Arm &a, const char *rest) {
  if (strcmp(rest, "STATE") == 0) {
    armState(a);
  } else if (strcmp(rest, "TORQUE ON") == 0) {
    armTorqueCmd(a, true);
  } else if (strcmp(rest, "TORQUE OFF") == 0) {
    armTorqueCmd(a, false);
  } else if (strncmp(rest, "SPEED ", 6) == 0) {
    a.speed = constrain(atoi(rest + 6), 50, 3000);
    Serial.print("ARM ");  Serial.print(a.side);
    Serial.print(" SPEED ");  Serial.println(a.speed);
  } else if (strncmp(rest, "MOVE ", 5) == 0) {
    int joint = -1, pos = -1;
    sscanf(rest + 5, "%d %d", &joint, &pos);
    armMove(a, joint, pos);
  } else {
    Serial.print("ERR arm_command ");  Serial.println(rest);
  }
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
  } else if (strcmp(cmd, "BUS SCAN") == 0) {
    busScan(7);
  } else if (strncmp(cmd, "BUS SCAN ", 9) == 0) {
    busScan(atoi(cmd + 9));
  } else if (strncmp(cmd, "BUS READ ", 9) == 0) {
    int id = -1, addr = -1, len = -1;
    sscanf(cmd + 9, "%d %d %d", &id, &addr, &len);
    busReadRaw(7, id, addr, len);
  } else if (strncmp(cmd, "ARM ", 4) == 0 && armBySide(cmd[4]) && cmd[5] == ' ') {
    armCommand(*armBySide(cmd[4]), cmd + 6);
  } else if (strncmp(cmd, "BUS SETID ", 10) == 0) {
    int from = -1, to = -1;
    sscanf(cmd + 10, "%d %d", &from, &to);
    busSetId(7, from, to);
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

  // Command the servos NOW. The loop only writes when the value changes, and
  // lastPanWritten/lastTiltWritten start equal to the target — so without this
  // the servos are never driven at boot. They hold whatever position they
  // powered up in while the firmware reports the centre, and the first nudge
  // then snaps them across the whole error in about a tenth of a second.
  servoPan.write(servoPanPos);
  writeTilt(servoTiltPos);

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

  // --- Smooth servo motion: time-based, speed-limited, 50 Hz ---
  uint32_t nowMs = millis();
  if (nowMs - lastServoUpdate >= SERVO_UPDATE_MS) {
    float dt = (nowMs - lastServoUpdate) / 1000.0f;
    lastServoUpdate = nowMs;
    if (dt > 0.2f) dt = 0.2f;             // after a stall, do not lurch

    servoPanCurrent  = easeToward(servoPanCurrent,  servoPanPos,  dt);
    servoTiltCurrent = easeToward(servoTiltCurrent, servoTiltPos, dt);

    int newPan = (int)(servoPanCurrent + 0.5);
    int newTilt = (int)(servoTiltCurrent + 0.5);

    if (newPan != lastPanWritten) {
      if (!panAttached) {                 // woken: drive it again
        servoPan.attach(SERVO_PAN_PIN);
        panAttached = true;
      }
      servoPan.write(newPan);
      lastPanWritten = newPan;
      panSettledAt = nowMs;
    } else if (panAttached && panSettledAt &&
               nowMs - panSettledAt > PAN_IDLE_DETACH_MS) {
      servoPan.detach();                  // settled and still: stop buzzing
      panAttached = false;
    }

    if (newTilt != lastTiltWritten) {
      writeTilt(newTilt);
      lastTiltWritten = newTilt;
    }
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
