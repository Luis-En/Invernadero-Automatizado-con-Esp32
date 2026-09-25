#include "simulator.h"

#if !defined(ESP8266)
#include <esp_system.h>
#endif

Simulator simulator;

namespace {
float uniform(float minValue, float maxValue) {
  return minValue + (random(0, 10001) / 10000.0f) * (maxValue - minValue);
}

float clampf(float value, float minValue, float maxValue) {
  if (value < minValue) return minValue;
  if (value > maxValue) return maxValue;
  return value;
}
}  // namespace

void Simulator::begin(uint32_t telemetryIntervalSec, uint32_t photoIntervalSec) {
#if defined(ESP8266)
  randomSeed(ESP.random());
#else
  randomSeed(esp_random());
#endif
  telemetry_interval_ms_ = telemetryIntervalSec * 1000UL;
  photo_interval_ms_ = photoIntervalSec * 1000UL;
  last_telemetry_ms_ = millis() - telemetry_interval_ms_;
  last_photo_ms_ = millis();
}

bool Simulator::dueTelemetry(uint32_t nowMs) {
  if (nowMs - last_telemetry_ms_ < telemetry_interval_ms_) {
    return false;
  }
  last_telemetry_ms_ = nowMs;
  return true;
}

bool Simulator::duePhoto(uint32_t nowMs) {
  if (nowMs - last_photo_ms_ < photo_interval_ms_) {
    return false;
  }
  last_photo_ms_ = nowMs;
  return true;
}

TelemetryData Simulator::nextTelemetry() {
  sequence_++;

  temperature_ = clampf(temperature_ + uniform(-0.3f, 0.3f), 18.0f, 35.0f);
  humidity_ = clampf(humidity_ + uniform(-1.5f, 1.5f), 40.0f, 95.0f);
  pressure_ = clampf(pressure_ + uniform(-0.5f, 0.5f), 990.0f, 1030.0f);

  TelemetryData telemetry;
  telemetry.epoch = 0;
  telemetry.temperature = temperature_;
  telemetry.humidity = humidity_;
  telemetry.pressure = pressure_;
  telemetry.sequence = sequence_;
  telemetry.rssi = (int8_t)(-random(40, 86));

  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    soil_[i] = clampf(soil_[i] + uniform(-1.0f, 1.0f), 0.0f, 100.0f);
    int adc = (int)(4095.0f * (1.0f - soil_[i] / 100.0f)) + random(-50, 51);
    bool ok = random(0, 100) >= 2;
    telemetry.soil[i].adc = (uint16_t)constrain(adc, 0, 4095);
    telemetry.soil[i].pct = ok ? soil_[i] : 0.0f;
    telemetry.soil[i].ok = ok;
  }

  // Mirrors config/actuators.yaml hysteresis defaults. Irrigation is disabled
  // by default in the seed config, so the pump stays off.
  if (temperature_ >= 30.0f) {
    fan_on_ = true;
  } else if (temperature_ <= 27.5f) {
    fan_on_ = false;
  }
  if (humidity_ <= 60.0f) {
    humidifier_on_ = true;
  } else if (humidity_ >= 68.0f) {
    humidifier_on_ = false;
  }

  telemetry.actuators[ACT_FAN_1] = fan_on_;
  telemetry.actuators[ACT_FAN_2] = fan_on_;
  telemetry.actuators[ACT_HUMIDIFIER_1] = humidifier_on_;
  telemetry.actuators[ACT_HUMIDIFIER_2] = humidifier_on_;
  telemetry.actuators[ACT_PUMP] = false;
  telemetry.device_id[0] = '\0';
  return telemetry;
}

void Simulator::beginPhoto() {
  static const uint8_t kHeader[] = {0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49,
                                    0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01};
  static const uint8_t kFooter[] = {0xFF, 0xD9};

  memcpy(photo_buffer_, kHeader, sizeof(kHeader));
  uint16_t offset = sizeof(kHeader);
  for (uint16_t i = 0; i < kPhotoBodyBytes; i++) {
    photo_buffer_[offset++] = (uint8_t)random(0, 256);
  }
  memcpy(photo_buffer_ + offset, kFooter, sizeof(kFooter));
  photo_length_ = offset + sizeof(kFooter);
}

uint16_t Simulator::photoChunkCount() const {
  if (photo_length_ == 0) {
    return 0;
  }
  return (uint16_t)((photo_length_ + kPhotoChunkBytes - 1) / kPhotoChunkBytes);
}

PhotoChunkData Simulator::nextPhotoChunk(uint16_t sequence, uint16_t index) const {
  PhotoChunkData chunk;
  memset(&chunk, 0, sizeof(chunk));
  chunk.sequence = sequence;
  chunk.total_chunks = photoChunkCount();
  chunk.chunk_index = index;

  uint16_t offset = index * kPhotoChunkBytes;
  uint16_t remaining = photo_length_ - offset;
  chunk.length = remaining > kPhotoChunkBytes ? kPhotoChunkBytes : remaining;
  memcpy(chunk.data, photo_buffer_ + offset, chunk.length);
  chunk.crc16 = crc16_ccitt(chunk.data, chunk.length);
  chunk.device_id[0] = '\0';
  return chunk;
}
