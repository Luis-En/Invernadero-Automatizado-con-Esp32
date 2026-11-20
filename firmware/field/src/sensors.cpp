#include "sensors.h"

#include <math.h>

#include "persistence.h"

#if !FIELD_NO_DHT
#include <DHT.h>
#endif

SensorManager sensors;

// A probe that repeats the same value for kStuckSamples cycles is treated as
// frozen. The epsilon is above normal ADC/LSB quantization but far below a
// real soil moisture change over 80 s.
static const float kSoilStuckEpsilon = 0.05f;

namespace {
#if !FIELD_NO_DHT
DHT dht(FIELD_DHT_PIN, FIELD_DHT_TYPE);
#endif

// Trimmed mean of a handful of ADC samples rejects a single bad conversion.
uint16_t readAdcAveraged(uint8_t pin) {
  uint32_t sum = 0;
  uint16_t min_value = 0xFFFF;
  uint16_t max_value = 0;
  for (uint8_t i = 0; i < SOIL_SAMPLES; i++) {
    uint16_t value = (uint16_t)analogRead(pin);
    sum += value;
    if (value < min_value) min_value = value;
    if (value > max_value) max_value = value;
    delayMicroseconds(200);
  }
  // Drop the extreme samples and average the rest.
  if (SOIL_SAMPLES > 2) {
    sum -= min_value;
    sum -= max_value;
    return (uint16_t)(sum / (SOIL_SAMPLES - 2));
  }
  return (uint16_t)(sum / SOIL_SAMPLES);
}

}  // namespace

void SensorManager::begin() {
  // Full 0-3.3 V range on ADC1. The default is usually 11 dB, but setting it
  // explicitly keeps the calibration valid across core versions.
  analogSetAttenuation(ADC_11db);

#if !FIELD_NO_DHT
  dht.begin();
  // The DHT11 needs about a second after power-up before it answers. Probe it
  // once so a missing sensor is visible on the console at boot instead of only
  // showing up as null telemetry later.
  delay(1200);
  const float probe_t = dht.readTemperature();
  const float probe_h = dht.readHumidity();
  dht_present_ = !isnan(probe_t) && !isnan(probe_h);
  if (dht_present_) {
    Serial.printf("[dht] ok on GPIO%d T=%.1fC H=%.0f%%\n", FIELD_DHT_PIN, probe_t,
                  probe_h);
  } else {
    Serial.printf(
        "[dht] no valid reading on GPIO%d (check 3.3 V, common GND, DATA and "
        "the 10k pull-up)\n",
        FIELD_DHT_PIN);
  }
#endif

  loadCalibration();
}

void SensorManager::resetStuck(StuckWindow& window) {
  window.index = 0;
  window.count = 0;
}

bool SensorManager::updateStuck(StuckWindow& window, float value, float epsilon) {
  if (isnan(value)) {
    resetStuck(window);
    return false;
  }
  window.samples[window.index] = value;
  window.index = (uint8_t)((window.index + 1) % kStuckSamples);
  if (window.count < kStuckSamples) {
    window.count++;
  }
  if (window.count < kStuckSamples) {
    return false;
  }
  float min_value = window.samples[0];
  float max_value = window.samples[0];
  for (uint8_t i = 1; i < kStuckSamples; i++) {
    if (window.samples[i] < min_value) min_value = window.samples[i];
    if (window.samples[i] > max_value) max_value = window.samples[i];
  }
  return (max_value - min_value) <= epsilon;
}

float SensorManager::readSoilPercent(uint8_t index, uint16_t adc) const {
  const Calibration& cal = calibration_[index];
  if (cal.dry_adc <= cal.wet_adc) {
    return NAN;
  }
  float span = (float)(cal.dry_adc - cal.wet_adc);
  float pct = ((float)cal.dry_adc - (float)adc) / span * 100.0f;
  if (pct < 0.0f) pct = 0.0f;
  if (pct > 100.0f) pct = 100.0f;
  return pct;
}

void SensorManager::read(SensorSnapshot& out) {
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
#if FIELD_SOIL_SCAN
    // Diagnostic scan: read every ADC1 pin and report the raw value even when
    // it is outside the plausible soil range, so a bench probe can be located.
    // GPIO25/26 are ADC2 and are unusable while the radio is active; skip
    // them instead of printing a misleading value.
    const uint8_t scan_pin = soil_pins_[i];
    if (scan_pin < 32 || scan_pin > 39) {
      out.soil[i].adc = 0;
      out.soil[i].ok = false;
      out.soil[i].pct = NAN;
      continue;
    }
    uint16_t adc = readAdcAveraged(scan_pin);
    out.soil[i].adc = adc;
    out.soil[i].ok = adc >= SOIL_ADC_MIN_VALID && adc <= SOIL_ADC_MAX_VALID;
    out.soil[i].pct = out.soil[i].ok ? readSoilPercent(i, adc) : NAN;
    if (out.soil[i].ok && updateStuck(soil_stuck_[i], out.soil[i].pct, kSoilStuckEpsilon)) {
      out.soil[i].ok = false;
      out.soil[i].pct = NAN;
    }
    continue;
#else
    // Skip probes that are not physically wired: report them invalid rather
    // than reading a floating pin as "disconnected every cycle".
    if ((FIELD_SOIL_MASK & (1 << i)) == 0) {
      out.soil[i].adc = 0;
      out.soil[i].ok = false;
      out.soil[i].pct = NAN;
      continue;
    }

    uint16_t adc = readAdcAveraged(soil_pins_[i]);
    out.soil[i].adc = adc;

    bool in_range = adc >= SOIL_ADC_MIN_VALID && adc <= SOIL_ADC_MAX_VALID;
    out.soil[i].ok = in_range;
    out.soil[i].pct = in_range ? readSoilPercent(i, adc) : NAN;
    if (in_range && updateStuck(soil_stuck_[i], out.soil[i].pct, kSoilStuckEpsilon)) {
      out.soil[i].ok = false;
      out.soil[i].pct = NAN;
    }
#endif
  }

  out.soil_any_valid = false;
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    if (out.soil[i].ok) {
      out.soil_any_valid = true;
      break;
    }
  }
  out.soil_average = soilAverage(out.soil, SOIL_SENSOR_COUNT);

#if FIELD_BENCH
  // Bench build: no DHT11 attached, synthesize plausible values.
  out.temperature = 25.0f + (float)(millis() % 60000) / 60000.0f * 5.0f;
  out.humidity = 70.0f;
#elif !FIELD_NO_DHT
  // A failed read returns NaN from the library; propagate it so the automation
  // fail-safe turns the humidifier off instead of trusting a bogus value.
  const float temperature = dht.readTemperature();
  const float humidity = dht.readHumidity();
  out.temperature = isnan(temperature) ? NAN : temperature;
  out.humidity = isnan(humidity) ? NAN : humidity;
  if (!isnan(out.temperature) && !isnan(out.humidity)) {
    dht_present_ = true;
  }
#else
  out.temperature = NAN;
  out.humidity = NAN;
#endif
}

void SensorManager::setCalibration(uint8_t index, uint16_t dry, uint16_t wet) {
  if (index >= SOIL_SENSOR_COUNT) {
    return;
  }
  if (dry > SOIL_ADC_MAX) dry = SOIL_ADC_MAX;
  calibration_[index].dry_adc = dry;
  calibration_[index].wet_adc = wet;
}

void SensorManager::resetCalibration() {
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    calibration_[i].dry_adc = SOIL_CAL_DRY_DEFAULT;
    calibration_[i].wet_adc = SOIL_CAL_WET_DEFAULT;
  }
}

uint16_t SensorManager::sampleRaw(uint8_t index) {
  if (index >= SOIL_SENSOR_COUNT) {
    return 0;
  }
  return readAdcAveraged(soil_pins_[index]);
}

void SensorManager::saveCalibration() {
  persistence.saveCalibration(calibration_, SOIL_SENSOR_COUNT);
}

void SensorManager::loadCalibration() {
  persistence.loadCalibration(calibration_, SOIL_SENSOR_COUNT);
}
