#include "config_pusher.h"

ConfigPusher configPusher;

void ConfigPusher::begin(EspNowHal* link) {
  link_ = link;
}

void ConfigPusher::fillHeader(EspNowHeader& header, uint8_t type) {
  header.magic = ESPNOW_MAGIC;
  header.version = ESPNOW_PROTO_VERSION;
  header.type = type;
  memcpy(header.src, link_->ownMac(), 6);
  header.seq = link_->nextSeq();
}

bool ConfigPusher::start(uint16_t version, const String& json, const uint8_t* mac) {
  if (link_ == nullptr || json.length() == 0) {
    return false;
  }
  payload_ = json;
  payload_crc_ = crc16_ccitt((const uint8_t*)payload_.c_str(), payload_.length());
  version_ = version;
  total_ = (uint16_t)((payload_.length() + ESPNOW_CMD_PAYLOAD_MAX - 1) / ESPNOW_CMD_PAYLOAD_MAX);
  if (total_ == 0) {
    total_ = 1;
  }
  next_index_ = 0;
  commit_attempts_ = 0;
  commit_sent_ = false;
  last_send_ms_ = 0;
  active_ = true;
  memcpy(mac_, mac, 6);
  return true;
}

bool ConfigPusher::sendChunk(uint16_t index) {
  CommandMsg msg;
  memset(&msg, 0, sizeof(msg));
  fillHeader(msg.hdr, MSG_COMMAND);
  msg.cmd = CMD_SET_CONFIG_CHUNK;
  msg.version = version_;
  msg.index = index;
  msg.total = total_;

  size_t offset = (size_t)index * ESPNOW_CMD_PAYLOAD_MAX;
  size_t remaining = payload_.length() - offset;
  uint16_t length = remaining > ESPNOW_CMD_PAYLOAD_MAX ? ESPNOW_CMD_PAYLOAD_MAX : (uint16_t)remaining;
  msg.payload_len = length;
  memcpy(msg.payload, payload_.c_str() + offset, length);

  return link_->send(mac_, (const uint8_t*)&msg, sizeof(msg));
}

bool ConfigPusher::sendCommit() {
  CommandMsg msg;
  memset(&msg, 0, sizeof(msg));
  fillHeader(msg.hdr, MSG_COMMAND);
  msg.cmd = CMD_SET_CONFIG_COMMIT;
  msg.version = version_;
  msg.index = 0;
  msg.total = total_;
  msg.arg = payload_crc_;
  msg.payload_len = 0;
  return link_->send(mac_, (const uint8_t*)&msg, sizeof(msg));
}

void ConfigPusher::tick() {
  if (!active_ || link_ == nullptr) {
    return;
  }

  if (next_index_ < total_) {
    for (uint8_t sent = 0; sent < kChunksPerTick && next_index_ < total_; sent++) {
      sendChunk(next_index_);
      next_index_++;
    }
    last_send_ms_ = millis();
    return;
  }

  if (!commit_sent_) {
    if (sendCommit()) {
      commit_sent_ = true;
      commit_attempts_ = 1;
      last_send_ms_ = millis();
    }
    return;
  }

  if (millis() - last_send_ms_ < kCommitRetryMs) {
    return;
  }
  if (commit_attempts_ >= kMaxCommitAttempts) {
    finish(false);
    return;
  }
  sendCommit();
  commit_attempts_++;
  last_send_ms_ = millis();
}

void ConfigPusher::onAck(uint8_t command, uint8_t status, uint16_t version) {
  if (!active_ || command != CMD_SET_CONFIG_COMMIT || version != version_) {
    return;
  }
  finish(status == 0);
}

void ConfigPusher::finish(bool ok) {
  active_ = false;
  if (result_callback_ != nullptr) {
    result_callback_(ok, version_);
  }
}
