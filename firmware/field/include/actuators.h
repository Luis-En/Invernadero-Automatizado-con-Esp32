#pragma once

#include <Arduino.h>

#include "automation.h"
#include "config.h"

// Drives the five output pins. The pins are active-high relay inputs behind an
// optocoupler/SSR as documented in config/actuators.yaml. On boot every pin is
// forced to its safe OFF level before anything else runs.
class ActuatorManager {
 public:
  void begin();
  void apply(const ActuatorState& state);
  void allOff();

  bool outputState(uint8_t index) const;

 private:
  void writePin(uint8_t index, bool on);
  bool output_state_[ACT_COUNT] = {false, false, false, false, false};
};

extern ActuatorManager actuators;
