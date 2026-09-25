#include "serial_link.h"

#include "config.h"
#include "json_builder.h"
#include "state_store.h"

SerialLink serialLink;

namespace {
void isoNow(char* out, size_t outLen) {
  state.formatIso(state.now(), out, outLen);
}
}  // namespace

void SerialLink::begin(unsigned long baud) {
  Serial.begin(baud);
}

void SerialLink::emit(JsonDocument& doc) {
  outbound_.remove(0);
  serializeJson(doc, outbound_);

  uint16_t crc = crc16_ccitt((const uint8_t*)outbound_.c_str(), outbound_.length());
  char suffix[8];
  snprintf(suffix, sizeof(suffix), "*%04X\n", crc);
  outbound_ += suffix;
  Serial.print(outbound_);
}

void SerialLink::sendHello() {
  DynamicJsonDocument doc(json_builder::kHelloCapacity);
  char timestamp[24];
  isoNow(timestamp, sizeof(timestamp));
  json_builder::hello(doc, GW_DEVICE_ID, GW_FW_VERSION, ESPNOW_PROTO_VERSION, millis() / 1000UL,
                      state.configVersion(), state.timeSynced(), GW_SIMULATE != 0, timestamp);
  emit(doc);
}

void SerialLink::sendTelemetry(const TelemetryData& telemetry) {
  DynamicJsonDocument doc(json_builder::kTelemetryCapacity);
  char timestamp[24];
  uint32_t epoch = telemetry.epoch != 0 ? telemetry.epoch : state.now();
  state.formatIso(epoch, timestamp, sizeof(timestamp));
  json_builder::telemetry(doc, telemetry, timestamp);
  emit(doc);
}

void SerialLink::sendPhotoChunk(const PhotoChunkData& chunk) {
  DynamicJsonDocument doc(json_builder::kPhotoChunkCapacity);
  json_builder::photoChunk(doc, chunk);
  emit(doc);
}

void SerialLink::sendDeviceStatus(const DeviceStatus& status) {
  DynamicJsonDocument doc(json_builder::kDeviceStatusCapacity);
  char timestamp[24];
  isoNow(timestamp, sizeof(timestamp));
  json_builder::deviceStatus(doc, status, timestamp);
  emit(doc);
}

void SerialLink::sendConfigAck(uint16_t version, uint8_t command, uint8_t status,
                               const char* message) {
  DynamicJsonDocument doc(json_builder::kConfigAckCapacity);
  char timestamp[24];
  isoNow(timestamp, sizeof(timestamp));
  json_builder::configAck(doc, version, command, status, message, timestamp);
  emit(doc);
}

void SerialLink::sendEvent(const char* severity, const char* code, const char* message) {
  DynamicJsonDocument doc(json_builder::kEventCapacity);
  char timestamp[24];
  isoNow(timestamp, sizeof(timestamp));
  json_builder::event(doc, severity, code, message, timestamp);
  emit(doc);
}

uint8_t SerialLink::parseTarget(const char* value) {
  if (value == nullptr) {
    return ROLE_FIELD;
  }
  if (strcmp(value, "camera") == 0) {
    return ROLE_CAMERA;
  }
  if (strcmp(value, "gateway") == 0) {
    return ROLE_GATEWAY;
  }
  return ROLE_FIELD;
}

void SerialLink::poll() {
  while (Serial.available() > 0) {
    int incoming = Serial.read();
    if (incoming < 0) {
      break;
    }
    if (incoming == '\n') {
      if (overflow_) {
        overflow_ = false;
        line_length_ = 0;
        sendEvent("warning", "SERIAL_OVERFLOW", "Inbound serial line exceeded buffer");
        continue;
      }
      if (line_length_ == 0) {
        continue;
      }
      line_buffer_[line_length_] = '\0';
      processLine(line_buffer_);
      line_length_ = 0;
      continue;
    }
    if (incoming == '\r') {
      continue;
    }
    if (line_length_ >= GW_MAX_SERIAL_LINE - 1) {
      overflow_ = true;
      continue;
    }
    line_buffer_[line_length_++] = (char)incoming;
  }
}

void SerialLink::processLine(char* line) {
  char* crcSeparator = strrchr(line, '*');
  if (crcSeparator != nullptr) {
    uint16_t expected = (uint16_t)strtoul(crcSeparator + 1, nullptr, 16);
    *crcSeparator = '\0';
    uint16_t actual = crc16_ccitt((const uint8_t*)line, strlen(line));
    if (expected != actual) {
      sendEvent("warning", "SERIAL_CRC", "Checksum mismatch on inbound serial line");
      return;
    }
  }

  inbound_.clear();
  DeserializationError error = deserializeJson(inbound_, line);
  if (error) {
    sendEvent("warning", "SERIAL_JSON", error.c_str());
    return;
  }

  const char* type = inbound_["type"] | "";
  InboundCommand command;

  if (strcmp(type, "set_config") == 0) {
    if (inbound_["config_json"].isNull()) {
      sendEvent("warning", "CONFIG_MISSING", "set_config without config_json");
      return;
    }
    command.kind = InboundKind::SetConfig;
    command.version = (uint16_t)(inbound_["version"] | (state.configVersion() + 1));
    command.target = parseTarget(inbound_["target"] | "field");
    serializeJson(inbound_["config_json"], command.config_json);
  } else if (strcmp(type, "timesync") == 0) {
    command.kind = InboundKind::Timesync;
    command.epoch = (uint32_t)inbound_["epoch"].as<unsigned long>();
  } else if (strcmp(type, "reboot") == 0) {
    command.kind = InboundKind::Reboot;
    command.target = parseTarget(inbound_["target"] | "field");
  } else if (strcmp(type, "purge") == 0) {
    command.kind = InboundKind::Purge;
    command.target = parseTarget(inbound_["target"] | "field");
  } else if (strcmp(type, "ping") == 0) {
    command.kind = InboundKind::Ping;
  } else {
    command.kind = InboundKind::Unknown;
  }

  if (callback_ != nullptr) {
    callback_(command);
  }
}
