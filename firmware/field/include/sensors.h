#pragma once

#include <Arduino.h>

#include "automation.h"
#include "config.h"
#include "config_model.h"

// Reads the 6 capacitive soil probes on ADC1 and the BME280 over I2C.
//
// Soil calibration: the sensors output a voltage that rises as the soil dries
// (and reads fall as it gets wet). Each probe stores a dry and a wet ADC value
// and the percentage is interpolated between them:
//     pct = (dry - adc) / (dry - wet) * 100
// Calibration values are persisted in NVS per sensor so a probe can be
// re-calibrated without touching the others.
class SensorManager {
 public:
  void begin();

  // Sample every sensor once and fill the snapshot.
  void read(SensorSnapshot& out);

  struct Calibration {
    uint16_t dry_adc = SOIL_ADC_MAX_VALID;
    uint16_t wet_adc = 1500;
  };

  const Calibration& calibration(uint8_t index) const { return calibration_[index]; }
  void setCalibration(uint8_t index, uint16_t dry, uint16_t wet);
  void saveCalibration();
  void loadCalibration();
  void resetCalibration();

  // BME280 presence is detected at begin(); when absent readings are NAN.
  bool bmePresent() const { return bme_present_; }

 private:
  float readSoilPercent(uint8_t index, uint16_t adc) const;

  uint8_t soil_pins_[SOIL_SENSOR_COUNT] = {
      SOIL_PIN_A1, SOIL_PIN_A2, SOIL_PIN_A3, SOIL_PIN_B1, SOIL_PIN_B2, SOIL_PIN_B3};
  Calibration calibration_[SOIL_SENSOR_COUNT];
  bool bme_present_ = false;
};

extern SensorManager sensors;
