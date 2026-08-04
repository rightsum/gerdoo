/*
  Teensy 4.1 — micro-ROS node over USB, with the debug console kept alive.

  Step 2 of the migration. Still touches no peripherals except the onboard LED:
  until the ACTION-PLAN section B bench measurements are done, driving any pin
  risks 5V into a part that clamps at 3.6V.

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
    publish   /teensy/heartbeat    std_msgs/Int32     seq, 1 Hz
    publish   /teensy/temperature  std_msgs/Float32   die temp C, 1 Hz
    subscribe /teensy/led          std_msgs/Bool      onboard LED

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

const char *FW_VERSION = "microros-0.1.0";
const int LED_PIN = 13;
const uint32_t HEARTBEAT_MS = 1000;

// How often to look for an agent while disconnected. Cheap ping, so half a
// second keeps reconnection prompt without flooding the link.
const uint32_t AGENT_PING_MS = 500;

rcl_allocator_t   allocator;
rclc_support_t    support;
rcl_node_t        node;
rclc_executor_t   executor;

rcl_publisher_t   pub_heartbeat;
rcl_publisher_t   pub_temperature;
rcl_subscription_t sub_led;

std_msgs__msg__Int32   msg_heartbeat;
std_msgs__msg__Float32 msg_temperature;
std_msgs__msg__Bool    msg_led;

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

  RCCHECK(rclc_subscription_init_default(
      &sub_led, &node,
      ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Bool), "teensy/led"));

  executor = rclc_executor_get_zero_initialized_executor();
  RCCHECK(rclc_executor_init(&executor, &support.context, 1, &allocator));
  RCCHECK(rclc_executor_add_subscription(
      &executor, &sub_led, &msg_led, &led_callback, ON_NEW_DATA));

  return true;
}

void destroyEntities() {
  // Stop the session from blocking on a dead link during teardown.
  rmw_context_t *rmw_context = rcl_context_get_rmw_context(&support.context);
  (void)rmw_uros_set_context_entity_destroy_session_timeout(rmw_context, 0);

  rcl_publisher_fini(&pub_heartbeat, &node);
  rcl_publisher_fini(&pub_temperature, &node);
  rcl_subscription_fini(&sub_led, &node);
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
  } else if (strncmp(cmd, "ECHO ", 5) == 0) {
    Serial.print("ECHO ");  Serial.println(cmd + 5);
  } else if (strcmp(cmd, "HELP") == 0) {
    Serial.println("HELP PING INFO HEALTH ROS ECHO <text> HELP");
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
  pollConsole();          // always works, in every agent state

  uint32_t now = millis();

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

    if (agentState == AGENT_CONNECTED) {
      msg_heartbeat.data   = (int32_t)heartbeatSeq;
      msg_temperature.data = tempmonGetTemp();
      RCSOFT(rcl_publish(&pub_heartbeat, &msg_heartbeat, NULL));
      RCSOFT(rcl_publish(&pub_temperature, &msg_temperature, NULL));
    }

    Serial.print("HEARTBEAT seq=");  Serial.print(heartbeatSeq);
    Serial.print(" uptime_ms=");     Serial.print(now - bootMillis);
    Serial.print(" temp_c=");        Serial.print(tempmonGetTemp(), 1);
    Serial.print(" loop_hz=");       Serial.print(loopsPerSec);
    Serial.print(" agent=");         Serial.print(agentStateName());
    Serial.println();
  }
}
