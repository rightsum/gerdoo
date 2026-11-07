// One drive motor: an IBT-2 (BTS7960) bridge and its Hall encoder. In its own
// header for the same reason as arm_types.h: the Arduino build generates
// prototypes for every sketch function at the top of the .ino, before any type
// declared inside it exists.
#pragma once
#include <stdint.h>
#include <QuadEncoder.h>

struct Drive {
  const char *name;      // "L" or "R"
  uint8_t rpwm, lpwm, en;
  QuadEncoder &enc;
  bool running;
  int targetDuty;        // signed, 12-bit; + drives RPWM, - drives LPWM
  int duty;              // on the pins now (ramped toward targetDuty)
  uint32_t startedAt, stopAt;
  int32_t encAtStart;
};
