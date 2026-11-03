#include "sensors.h"

#include <math.h>

#include "persistence.h"

#if !FIELD_NO_BME280
#include <Adafruit_BME280.h>
#include <Wire.h>
#endif

SensorManager sensors;

namespace {
#if !FIELD_NO_BME280
Adafruit_BME280 bme;
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

#if !FIELD_NO_BME280
// Prints every device that answers on the I2C bus. Makes a mis-wired or
// unpowered BME280 obvious on the serial console instead of a silent NaN.
void scanI2cBus() {
  Serial.println("[bme] I2C scan:");
  uint8_t found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("[bme]   device at 0x%02X\n", addr);
      found++;
    }
  }
  if (found == 0) {
    Serial.println("[bme]   no devices found");
  }
}
#endif
}  // namespace

void SensorManager::begin() {
  // Full 0-3.3 V range on ADC1. The default is usually 11 dB, but setting it
  // explicitly keeps the calibration valid across core versions.
  analogSetAttenuation(ADC_11db);

#if !FIELD_NO_BME280
  // 6-pin BME280: strap it into I2C mode only if the breakout leaves CSB/SDO
  // for the host to drive. A value of -1 means the board ties them itself.
#if FIELD_BME280_CSB_PIN >= 0
  pinMode(FIELD_BME280_CSB_PIN, OUTPUT);
  digitalWrite(FIELD_BME280_CSB_PIN, HIGH);
#endif
#if FIELD_BME280_SDO_PIN >= 0
  pinMode(FIELD_BME280_SDO_PIN, OUTPUT);
  digitalWrite(FIELD_BME280_SDO_PIN, LOW);
#endif
  delay(5);

  Wire.begin(FIELD_I2C_SDA, FIELD_I2C_SCL);
  delay(10);
  scanI2cBus();
  bme_present_ = bme.begin(FIELD_BME280_ADDR, &Wire) || bme.begin(0x77, &Wire);

  if (!bme_present_) {
    // SDA/SCL swapped is the most common wiring mistake. The BME280 is I2C
    // only here (CSB/SDO are not driven), so retrying the other orientation
    // costs nothing and saves a reflash.
    Serial.println("[bme] not found, retrying with SDA/SCL swapped");
    Wire.end();
    Wire.begin(FIELD_I2C_SCL, FIELD_I2C_SDA);
    delay(10);
    scanI2cBus();
    bme_present_ = bme.begin(FIELD_BME280_ADDR, &Wire) || bme.begin(0x77, &Wire);
  }

  if (bme_present_) {
    bme.setSampling(Adafruit_BME280::MODE_FORCED,
                    Adafruit_BME280::SAMPLING_X2,
                    Adafruit_BME280::SAMPLING_X16,
                    Adafruit_BME280::SAMPLING_X1,
                    Adafruit_BME280::FILTER_X16,
                    Adafruit_BME280::STANDBY_MS_500);
  }
#endif

  loadCalibration();
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
    // Diagnostic scan: read every pin and report the raw ADC even when it is
    // outside the plausible soil range, so a bench probe can be located.
    uint16_t adc = readAdcAveraged(soil_pins_[i]);
    out.soil[i].adc = adc;
    out.soil[i].ok = adc >= SOIL_ADC_MIN_VALID && adc <= SOIL_ADC_MAX_VALID;
    out.soil[i].pct = out.soil[i].ok ? readSoilPercent(i, adc) : NAN;
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
  // Bench build: no BME280 attached, synthesize plausible values.
  out.temperature = 25.0f + (float)(millis() % 60000) / 60000.0f * 5.0f;
  out.humidity = 70.0f;
  out.pressure = 1013.0f;
#elif !FIELD_NO_BME280
  if (bme_present_) {
    out.temperature = bme.readTemperature();
    out.humidity = bme.readHumidity();
    out.pressure = bme.readPressure() / 100.0f;
    if (isnan(out.temperature)) out.temperature = NAN;
    if (isnan(out.humidity)) out.humidity = NAN;
    if (isnan(out.pressure)) out.pressure = NAN;
  } else {
    out.temperature = NAN;
    out.humidity = NAN;
    out.pressure = NAN;
  }
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
