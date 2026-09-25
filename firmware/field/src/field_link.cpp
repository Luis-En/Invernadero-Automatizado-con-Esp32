#include "field_link.h"

#include <math.h>

#include "espnow_hal.h"

FieldLink fieldLink;

void FieldLink::begin(ConfigAppliedCallback on_config) {
  config_callback_ = on_config;
  resetConfigAssembly();
}

void FieldLink::resetConfigAssembly() {
  config_version_ = 0;
  config_expected_crc_ = 0;
  config_total_chunks_ = 0;
  config_received_chunks_ = 0;
  config_buffer_len_ = 0;
}

void FieldLink::copyDeviceId(char* out, size_t out_size) {
  strncpy(out, FIELD_DEVICE_ID, out_size - 1);
  out[out_size - 1] = '\0';
}

void FieldLink::poll(uint32_t now_ms) {
  EspNowMessage frame;
  while (espNow.poll(frame, 0)) {
    handleFrame(frame);
  }
  (void)now_ms;
}

void FieldLink::sendHello(uint32_t now_ms) {
  HelloMsg msg;
  memset(&msg, 0, sizeof(msg));
  msg.hdr.magic = ESPNOW_MAGIC;
  msg.hdr.version = ESPNOW_PROTO_VERSION;
  msg.hdr.type = MSG_HELLO;
  memcpy(msg.hdr.src, espNow.ownMac(), 6);
  msg.hdr.seq = espNow.nextSeq();
  msg.role = ROLE_FIELD;
  msg.fw_major = FIELD_FW_VERSION_MAJOR;
  msg.fw_minor = FIELD_FW_VERSION_MINOR;
  msg.fw_patch = FIELD_FW_VERSION_PATCH;
  msg.uptime_s = now_ms / 1000UL;
  copyDeviceId(msg.device_id, sizeof(msg.device_id));
  espNow.sendBroadcast((const uint8_t*)&msg, sizeof(msg));
}

void FieldLink::sendTelemetry(const TelemetryData& telemetry) {
  TelemetryMsg msg;
  memset(&msg, 0, sizeof(msg));
  msg.hdr.magic = ESPNOW_MAGIC;
  msg.hdr.version = ESPNOW_PROTO_VERSION;
  msg.hdr.type = MSG_TELEMETRY;
  memcpy(msg.hdr.src, espNow.ownMac(), 6);
  msg.hdr.seq = espNow.nextSeq();

  msg.epoch = telemetry.epoch;

  // NaN/Inf must never be cast to an integer: lroundf(NAN) is undefined and
  // produced garbage such as 0xFFFF on the wire. Emit 0 for missing readings;
  // the consumer treats 0 as "no data" for temperature/humidity/pressure.
  msg.temperature_c_x100 = isnan(telemetry.temperature) || isinf(telemetry.temperature)
                               ? 0
                               : (int16_t)lroundf(telemetry.temperature * 100.0f);
  msg.humidity_pct_x100 = isnan(telemetry.humidity) || isinf(telemetry.humidity)
                              ? 0
                              : (uint16_t)lroundf(telemetry.humidity * 100.0f);
  msg.pressure_hpa = isnan(telemetry.pressure) || isinf(telemetry.pressure)
                         ? 0
                         : (uint16_t)lroundf(telemetry.pressure);

  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    msg.soil_adc[i] = telemetry.soil[i].adc;
    float pct = telemetry.soil[i].pct;
    msg.soil_pct[i] = (isnan(pct) || isinf(pct)) ? 0 : (uint8_t)lroundf(pct);
  }
  uint8_t mask = 0;
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    if (telemetry.soil[i].ok) {
      mask |= (uint8_t)(1 << i);
    }
  }
  msg.soil_ok_mask = mask;

  uint8_t act_mask = 0;
  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    if (telemetry.actuators[i]) {
      act_mask |= (uint8_t)(1 << i);
    }
  }
  msg.actuator_mask = act_mask;
  msg.rssi = telemetry.rssi;

  // Send to the gateway. If the gateway MAC is unknown, broadcast so it is
  // discovered and can reply with a command.
  espNow.sendBroadcast((const uint8_t*)&msg, sizeof(msg));
}

void FieldLink::sendAck(uint16_t ack_seq, uint8_t command, uint16_t version, uint8_t status) {
  AckMsg msg;
  memset(&msg, 0, sizeof(msg));
  msg.hdr.magic = ESPNOW_MAGIC;
  msg.hdr.version = ESPNOW_PROTO_VERSION;
  msg.hdr.type = MSG_ACK;
  memcpy(msg.hdr.src, espNow.ownMac(), 6);
  msg.hdr.seq = espNow.nextSeq();
  msg.ack_seq = ack_seq;
  msg.cmd = command;
  msg.version = version;
  msg.status = status;
  espNow.sendBroadcast((const uint8_t*)&msg, sizeof(msg));
}

void FieldLink::sendEvent(uint8_t severity, const char* code, const char* message) {
  EventMsg msg;
  memset(&msg, 0, sizeof(msg));
  msg.hdr.magic = ESPNOW_MAGIC;
  msg.hdr.version = ESPNOW_PROTO_VERSION;
  msg.hdr.type = MSG_EVENT;
  memcpy(msg.hdr.src, espNow.ownMac(), 6);
  msg.hdr.seq = espNow.nextSeq();
  msg.severity = severity;
  msg.role = ROLE_FIELD;
  strncpy(msg.code, code != nullptr ? code : "", sizeof(msg.code) - 1);
  strncpy(msg.message, message != nullptr ? message : "", sizeof(msg.message) - 1);
  espNow.sendBroadcast((const uint8_t*)&msg, sizeof(msg));
}

void FieldLink::syncEpoch(uint32_t epoch) {
  time_synced_ = true;
  epoch_base_ = epoch;
  epoch_base_ms_ = millis();
}

uint32_t FieldLink::epochNow() const {
  if (!time_synced_) {
    return 0;
  }
  return epoch_base_ + (millis() - epoch_base_ms_) / 1000UL;
}

void FieldLink::handleFrame(const EspNowMessage& frame) {
  if (frame.length < sizeof(EspNowHeader)) {
    return;
  }
  EspNowHeader header;
  memcpy(&header, frame.data, sizeof(header));
  if (header.magic != ESPNOW_MAGIC || header.version != ESPNOW_PROTO_VERSION) {
    return;
  }
  if (header.type == MSG_COMMAND && frame.length >= sizeof(CommandMsg)) {
    CommandMsg msg;
    memcpy(&msg, frame.data, sizeof(msg));
    handleCommand(msg);
  }
}

void FieldLink::handleCommand(const CommandMsg& msg) {
  switch (msg.cmd) {
    case CMD_SET_CONFIG_CHUNK:
      handleConfigChunk(msg);
      break;
    case CMD_SET_CONFIG_COMMIT:
      handleConfigCommit(msg);
      break;
    case CMD_TIMESYNC:
      syncEpoch(msg.arg);
      sendAck(msg.hdr.seq, CMD_TIMESYNC, 0, 0);
      break;
    case CMD_REBOOT:
      sendAck(msg.hdr.seq, CMD_REBOOT, 0, 0);
      delay(100);
      ESP.restart();
      break;
    case CMD_PURGE:
      resetConfigAssembly();
      sendAck(msg.hdr.seq, CMD_PURGE, 0, 0);
      break;
    case CMD_PING:
      sendAck(msg.hdr.seq, CMD_PING, 0, 0);
      break;
    default:
      sendAck(msg.hdr.seq, msg.cmd, 0, 1);
      break;
  }
}

void FieldLink::handleConfigChunk(const CommandMsg& msg) {
  if (msg.total == 0 || msg.index >= msg.total) {
    sendAck(msg.hdr.seq, CMD_SET_CONFIG_CHUNK, msg.version, 1);
    return;
  }

  // A new push starts at index 0 or when the version changes.
  if (msg.index == 0) {
    resetConfigAssembly();
    config_version_ = msg.version;
    config_total_chunks_ = msg.total;
  } else if (config_version_ == 0 || msg.version != config_version_ || msg.total != config_total_chunks_) {
    // Out-of-order chunk for an unknown push: ignore it.
    sendAck(msg.hdr.seq, CMD_SET_CONFIG_CHUNK, msg.version, 1);
    return;
  }

  if (msg.payload_len > ESPNOW_CMD_PAYLOAD_MAX) {
    sendAck(msg.hdr.seq, CMD_SET_CONFIG_CHUNK, msg.version, 1);
    return;
  }
  if (config_buffer_len_ + msg.payload_len >= kConfigBufferMax) {
    // Would overflow the assembly buffer; abort the push safely.
    resetConfigAssembly();
    sendAck(msg.hdr.seq, CMD_SET_CONFIG_CHUNK, msg.version, 1);
    return;
  }

  memcpy(config_buffer_ + config_buffer_len_, msg.payload, msg.payload_len);
  config_buffer_len_ += msg.payload_len;
  config_received_chunks_++;

  sendAck(msg.hdr.seq, CMD_SET_CONFIG_CHUNK, msg.version, 0);
}

void FieldLink::handleConfigCommit(const CommandMsg& msg) {
  // The commit frame carries the CRC of the whole document in `arg` (lower 16
  // bits) and its version. It is only accepted once every chunk arrived.
  uint16_t expected_crc = (uint16_t)(msg.arg & 0xFFFF);

  if (config_buffer_len_ == 0 || config_total_chunks_ == 0 ||
      config_received_chunks_ != config_total_chunks_) {
    resetConfigAssembly();
    sendAck(msg.hdr.seq, CMD_SET_CONFIG_COMMIT, msg.version, 1);
    return;
  }

  uint16_t actual_crc = configCrc16(config_buffer_, config_buffer_len_);
  if (actual_crc != expected_crc) {
    resetConfigAssembly();
    sendAck(msg.hdr.seq, CMD_SET_CONFIG_COMMIT, msg.version, 2);
    return;
  }

  RuntimeConfig config;
  if (!config.fromJson(config_buffer_, config_buffer_len_)) {
    resetConfigAssembly();
    sendAck(msg.hdr.seq, CMD_SET_CONFIG_COMMIT, msg.version, 3);
    return;
  }

  config.version = msg.version;
  sendAck(msg.hdr.seq, CMD_SET_CONFIG_COMMIT, msg.version, 0);
  resetConfigAssembly();

  if (config_callback_ != nullptr) {
    config_callback_(config);
  }
}
