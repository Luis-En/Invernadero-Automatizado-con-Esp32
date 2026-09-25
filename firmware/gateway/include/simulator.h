#pragma once

#include <Arduino.h>

#include "protocol.h"

// Synthetic field/camera source used when the firmware is built for the
// gateway_sim environment. It mirrors the Python serial bridge simulator so a
// bare gateway can drive the whole Raspberry Pi pipeline on a bench.
class Simulator {
 public:
  void begin(uint32_t telemetryIntervalSec, uint32_t photoIntervalSec);

  bool dueTelemetry(uint32_t nowMs);
  bool duePhoto(uint32_t nowMs);

  TelemetryData nextTelemetry();
  uint16_t nextPhotoSequence() { return ++photo_sequence_; }
  void beginPhoto();
  uint16_t photoChunkCount() const;
  PhotoChunkData nextPhotoChunk(uint16_t sequence, uint16_t index) const;

 private:
  static const uint16_t kPhotoBodyBytes = 4096;
  static const uint16_t kPhotoChunkBytes = ESPNOW_PHOTO_DATA_MAX;
  static const uint16_t kPhotoBufferMax = 18 + kPhotoBodyBytes + 2;

  float temperature_ = 26.5f;
  float humidity_ = 72.0f;
  float pressure_ = 1013.2f;
  float soil_[SOIL_SENSOR_COUNT] = {45.0f, 42.0f, 48.0f, 40.0f, 44.0f, 38.0f};
  bool fan_on_ = false;
  bool humidifier_on_ = false;

  uint16_t sequence_ = 0;
  uint16_t photo_sequence_ = 0;
  uint32_t telemetry_interval_ms_ = 30000;
  uint32_t photo_interval_ms_ = 1800000;
  uint32_t last_telemetry_ms_ = 0;
  uint32_t last_photo_ms_ = 0;

  uint8_t photo_buffer_[kPhotoBufferMax];
  uint16_t photo_length_ = 0;
};

extern Simulator simulator;
