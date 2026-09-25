#pragma once

#include <Arduino.h>

#include "config.h"
#include "config_model.h"
#include "protocol.h"

// C++ port of backend/api/app/automation.py. Keeping the exact same rules on
// the node is what makes the greenhouse safe when the Pi is unreachable:
//  1. A sensor reading that is missing or out of physical range forces the
//     related actuator OFF. A broken sensor must never hold an actuator ON.
//  2. Hysteresis: actuators switch ON and OFF at different thresholds so the
//     relays do not chatter around a single setpoint.
//  3. Hard limits: every actuator has a maximum continuous ON time.

static const float TEMP_MIN_VALID = -10.0f;
static const float TEMP_MAX_VALID = 60.0f;
static const float HUM_MIN_VALID = 0.0f;
static const float HUM_MAX_VALID = 100.0f;

// Soil samples as read from the ADC plus calibration.
struct SoilReading {
  uint16_t adc = 0;
  float pct = 0.0f;
  bool ok = false;
};

// Sensor snapshot used by the automation pass.
struct SensorSnapshot {
  float temperature = NAN;   // NAN means "no valid reading"
  float humidity = NAN;
  float pressure = NAN;
  SoilReading soil[SOIL_SENSOR_COUNT];
  bool soil_any_valid = false;
  float soil_average = NAN;
};

bool validTemperature(float value);
bool validHumidity(float value);
bool validSoil(float value);

// State of the five actuators plus how long each has been continuously ON.
struct ActuatorState {
  bool fan_1 = false;
  bool fan_2 = false;
  bool humidifier_1 = false;
  bool humidifier_2 = false;
  bool pump = false;

  uint32_t on_since_ms[ACT_COUNT] = {0, 0, 0, 0, 0};

  bool get(uint8_t index) const;
  void set(uint8_t index, bool value);
};

// Compute the full actuator state set for one control cycle, given the current
// config, sensor snapshot, previous states and a manual override mask/value.
// `now_ms` is used for the max-ON limits.
void computeActuatorStates(const RuntimeConfig& config,
                           const SensorSnapshot& sensors,
                           ActuatorState& state,
                           uint32_t now_ms,
                           bool manual_override_active,
                           const bool manual_values[ACT_COUNT]);

// Average of the valid soil samples, or NAN when none are valid.
float soilAverage(const SoilReading* readings, size_t count);
