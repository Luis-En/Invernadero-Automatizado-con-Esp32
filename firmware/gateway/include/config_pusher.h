#pragma once

#include <Arduino.h>

#include "espnow_hal.h"
#include "protocol.h"

// Pushes a configuration JSON to the field node over ESP-NOW. ESP-NOW frames
// are capped at 250 bytes while a config can be larger, so the payload is
// split into chunks followed by a commit frame carrying the CRC of the whole
// document. The field node only applies the config after a valid commit.
class ConfigPusher {
 public:
  using ResultCallback = void (*)(bool ok, uint16_t version);

  void begin(EspNowHal* link);
  void setResultCallback(ResultCallback callback) { result_callback_ = callback; }

  bool start(uint16_t version, const String& json, const uint8_t* mac);
  void tick();
  void onAck(uint8_t command, uint8_t status, uint16_t version);
  bool active() const { return active_; }
  uint16_t version() const { return version_; }

 private:
  static const uint8_t kMaxCommitAttempts = 4;
  static const uint32_t kCommitRetryMs = 2000;
  static const uint8_t kChunksPerTick = 2;

  bool sendChunk(uint16_t index);
  bool sendCommit();
  void finish(bool ok);
  void fillHeader(EspNowHeader& header, uint8_t type);

  EspNowHal* link_ = nullptr;
  ResultCallback result_callback_ = nullptr;
  bool active_ = false;
  bool commit_sent_ = false;
  uint16_t version_ = 0;
  uint16_t total_ = 0;
  uint16_t next_index_ = 0;
  uint8_t mac_[6] = {0};
  String payload_;
  uint16_t payload_crc_ = 0;
  uint32_t last_send_ms_ = 0;
  uint8_t commit_attempts_ = 0;
};

extern ConfigPusher configPusher;
