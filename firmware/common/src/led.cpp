#include "led.h"

void Led::begin(uint8_t pin, bool activeLow) {
  pin_ = pin;
  active_low_ = activeLow;
  pinMode(pin_, OUTPUT);
  set(false);
}

void Led::write(bool on) {
  digitalWrite(pin_, (on != active_low_) ? HIGH : LOW);
}

void Led::set(bool on) {
  state_ = on;
  write(on);
}

void Led::toggle() {
  set(!state_);
}
