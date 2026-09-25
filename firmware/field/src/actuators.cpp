#include "actuators.h"

ActuatorManager actuators;

namespace {
const uint8_t kPins[ACT_COUNT] = {
    ACT_PIN_FAN_1, ACT_PIN_FAN_2, ACT_PIN_HUMIDIFIER_1, ACT_PIN_HUMIDIFIER_2, ACT_PIN_PUMP};

bool activeHigh(uint8_t index) {
  switch (index) {
    case ACT_FAN_1:
    case ACT_FAN_2: return ACT_FAN_ACTIVE_HIGH != 0;
    case ACT_HUMIDIFIER_1:
    case ACT_HUMIDIFIER_2: return ACT_HUMIDIFIER_ACTIVE_HIGH != 0;
    case ACT_PUMP: return ACT_PUMP_ACTIVE_HIGH != 0;
    default: return true;
  }
}
}  // namespace

void ActuatorManager::begin() {
  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    pinMode(kPins[i], OUTPUT);
  }
  allOff();
}

void ActuatorManager::writePin(uint8_t index, bool on) {
  bool level = activeHigh(index) ? on : !on;
  digitalWrite(kPins[index], level ? HIGH : LOW);
  output_state_[index] = on;
}

void ActuatorManager::allOff() {
  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    writePin(i, false);
  }
}

void ActuatorManager::apply(const ActuatorState& state) {
  writePin(ACT_FAN_1, state.fan_1);
  writePin(ACT_FAN_2, state.fan_2);
  writePin(ACT_HUMIDIFIER_1, state.humidifier_1);
  writePin(ACT_HUMIDIFIER_2, state.humidifier_2);
  writePin(ACT_PUMP, state.pump);
}

bool ActuatorManager::outputState(uint8_t index) const {
  if (index >= ACT_COUNT) {
    return false;
  }
  return output_state_[index];
}
