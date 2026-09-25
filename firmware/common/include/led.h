#pragma once

#include <Arduino.h>

// Simple LED driver that understands active-high and active-low wiring.
class Led {
 public:
  void begin(uint8_t pin, bool activeLow);
  void set(bool on);
  void toggle();
  bool state() const { return state_; }

 private:
  void write(bool on);

  uint8_t pin_ = 0;
  bool active_low_ = false;
  bool state_ = false;
};
