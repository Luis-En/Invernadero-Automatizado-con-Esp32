#include "automation.h"

#include <math.h>

bool validTemperature(float value) {
  return !isnan(value) && value >= TEMP_MIN_VALID && value <= TEMP_MAX_VALID;
}

bool validHumidity(float value) {
  return !isnan(value) && value >= HUM_MIN_VALID && value <= HUM_MAX_VALID;
}

bool validSoil(float value) {
  return !isnan(value) && value >= 0.0f && value <= 100.0f;
}

bool ActuatorState::get(uint8_t index) const {
  switch (index) {
    case ACT_FAN_1: return fan_1;
    case ACT_FAN_2: return fan_2;
    case ACT_HUMIDIFIER_1: return humidifier_1;
    case ACT_HUMIDIFIER_2: return humidifier_2;
    case ACT_PUMP: return pump;
    default: return false;
  }
}

void ActuatorState::set(uint8_t index, bool value) {
  switch (index) {
    case ACT_FAN_1: fan_1 = value; break;
    case ACT_FAN_2: fan_2 = value; break;
    case ACT_HUMIDIFIER_1: humidifier_1 = value; break;
    case ACT_HUMIDIFIER_2: humidifier_2 = value; break;
    case ACT_PUMP: pump = value; break;
    default: break;
  }
}

// Turn-on-when-low actuators (humidifier, pump): ON below `on`, OFF above `off`.
static bool decideLow(bool current, float value, float on, float off) {
  if (isnan(value)) {
    return false;
  }
  if (!current && value <= on) {
    return true;
  }
  if (current && value >= off) {
    return false;
  }
  return current;
}

// Turn-on-when-high actuators (fans): ON at/above `on`, OFF at/below `off`.
static bool decideHigh(bool current, float value, float on, float off) {
  if (isnan(value)) {
    return false;
  }
  if (!current && value >= on) {
    return true;
  }
  if (current && value <= off) {
    return false;
  }
  return current;
}

static bool exceedsLimit(bool state, uint32_t on_since_ms, uint32_t limit_s, uint32_t now_ms) {
  if (!state || limit_s == 0) {
    return false;
  }
  return (now_ms - on_since_ms) >= (limit_s * 1000UL);
}

void computeActuatorStates(const RuntimeConfig& config,
                           const SensorSnapshot& sensors,
                           ActuatorState& state,
                           uint32_t now_ms,
                           bool manual_override_active,
                           const bool manual_values[ACT_COUNT]) {
  // Remember previous states to detect transitions for the ON-timer.
  const bool prev[ACT_COUNT] = {
      state.fan_1, state.fan_2, state.humidifier_1, state.humidifier_2, state.pump};

  // --- Ventilation (temperature driven) ------------------------------------
  bool fan;
  if (!validTemperature(sensors.temperature)) {
    fan = false;
  } else {
    fan = decideHigh(state.fan_1, sensors.temperature, config.temp.on, config.temp.off);
  }
  state.fan_1 = fan;
  state.fan_2 = fan;

  // --- Humidifiers (ambient humidity driven) ------------------------------
  bool humidifier;
  if (!validHumidity(sensors.humidity)) {
    humidifier = false;
  } else {
    humidifier = decideLow(state.humidifier_1, sensors.humidity, config.humidity.on, config.humidity.off);
  }
  state.humidifier_1 = humidifier;
  state.humidifier_2 = humidifier;

  // --- Pump (soil moisture driven) ----------------------------------------
  if (!config.irrigation_enabled || !validSoil(sensors.soil_average)) {
    state.pump = false;
  } else {
    state.pump = decideLow(state.pump, sensors.soil_average, config.soil.on, config.soil.off);
  }

  // --- Hard maximum ON time ------------------------------------------------
  if (exceedsLimit(state.fan_1, state.on_since_ms[ACT_FAN_1], config.max_on_fan_s, now_ms)) {
    state.fan_1 = false;
  }
  if (exceedsLimit(state.fan_2, state.on_since_ms[ACT_FAN_2], config.max_on_fan_s, now_ms)) {
    state.fan_2 = false;
  }
  if (exceedsLimit(state.humidifier_1, state.on_since_ms[ACT_HUMIDIFIER_1], config.max_on_humidifier_s, now_ms)) {
    state.humidifier_1 = false;
  }
  if (exceedsLimit(state.humidifier_2, state.on_since_ms[ACT_HUMIDIFIER_2], config.max_on_humidifier_s, now_ms)) {
    state.humidifier_2 = false;
  }
  if (exceedsLimit(state.pump, state.on_since_ms[ACT_PUMP], config.max_on_pump_s, now_ms)) {
    state.pump = false;
  }

  // --- Manual override (admin) --------------------------------------------
  if (manual_override_active) {
    for (uint8_t i = 0; i < ACT_COUNT; i++) {
      state.set(i, manual_values[i]);
    }
  }

  // --- Update the continuous-ON timers ------------------------------------
  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    bool now_on = state.get(i);
    if (now_on && !prev[i]) {
      state.on_since_ms[i] = now_ms;
    } else if (!now_on) {
      state.on_since_ms[i] = 0;
    }
  }
}

float soilAverage(const SoilReading* readings, size_t count) {
  float sum = 0.0f;
  size_t valid = 0;
  for (size_t i = 0; i < count; i++) {
    if (readings[i].ok && validSoil(readings[i].pct)) {
      sum += readings[i].pct;
      valid++;
    }
  }
  if (valid == 0) {
    return NAN;
  }
  return sum / (float)valid;
}
