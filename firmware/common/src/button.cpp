#include "button.h"

void Button::begin(uint8_t pin, uint32_t debounceMs) {
  pin_ = pin;
  debounce_ms_ = debounceMs;
  pinMode(pin_, INPUT_PULLUP);
  raw_ = digitalRead(pin_) == LOW;
  pressed_ = raw_;
  last_change_ms_ = millis();
}

bool Button::update() {
  bool reading = digitalRead(pin_) == LOW;
  if (reading != raw_) {
    raw_ = reading;
    last_change_ms_ = millis();
  }

  if ((millis() - last_change_ms_) >= debounce_ms_ && pressed_ != raw_) {
    pressed_ = raw_;
    return true;
  }
  return false;
}
