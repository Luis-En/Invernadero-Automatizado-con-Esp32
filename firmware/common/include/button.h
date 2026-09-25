#pragma once

#include <Arduino.h>

// Push button wired between the pin and GND. Uses the internal pull-up, so a
// pressed button reads LOW. update() reports debounced state changes.
class Button {
 public:
  void begin(uint8_t pin, uint32_t debounceMs = 30);
  bool update();
  bool pressed() const { return pressed_; }

 private:
  uint8_t pin_ = 0;
  uint32_t debounce_ms_ = 30;
  bool raw_ = false;
  bool pressed_ = false;
  uint32_t last_change_ms_ = 0;
};
