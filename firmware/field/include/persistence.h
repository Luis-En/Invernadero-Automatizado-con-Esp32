#pragma once

#include <Arduino.h>

#include "config.h"
#include "config_model.h"
#include "sensors.h"

// NVS-backed persistence. The field node must keep the last valid
// configuration and per-probe calibration across power cuts, so both live in
// the ESP32 Preferences partition.
//
// Preferences is chosen over raw EEPROM because it does wear levelling and
// namespaced key/value storage, and it survives OTA updates.
class Persistence {
 public:
  void begin();

  bool saveConfig(const RuntimeConfig& config);
  bool loadConfig(RuntimeConfig& out);
  bool hasConfig();

  bool saveCalibration(const SensorManager::Calibration* calibration, size_t count);
  bool loadCalibration(SensorManager::Calibration* out, size_t count);

  void clear();

 private:
  bool ready_ = false;
};

extern Persistence persistence;
