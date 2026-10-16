// One ElRobot follower arm on the servo bus. In its own header because the
// Arduino build generates prototypes for every sketch function at the top of
// the .ino, before any type declared inside it exists.
#pragma once
#include <stdint.h>

struct Arm {
  char side;          // 'L' or 'R'
  uint8_t firstId;    // L = 1..8, R = 11..18
  bool torque;        // as last read back from the servos
  uint16_t speed;     // goal speed, steps/s
  uint16_t strength;  // torque limit, 0-1000 (1000 = the servo's full torque)
  uint8_t seamTrips;  // joints the seam watchdog stopped since the last STATE, bit per joint
  int16_t lo[8];      // joint limits in display readings, from the Teensy's EEPROM;
  int16_t hi[8];      // 0..4095 = uncalibrated
};
