#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>

#include "config.h"
#include "protocol.h"

enum class InboundKind : uint8_t {
  SetConfig,
  Timesync,
  Reboot,
  Purge,
  Ping,
  SetActuator,
  Unknown,
};

struct InboundCommand {
  InboundKind kind = InboundKind::Unknown;
  uint16_t version = 0;
  uint32_t epoch = 0;
  uint8_t target = ROLE_FIELD;
  String config_json;
  char actuator[16] = {0};
  bool state = false;
  char command_id[40] = {0};
};

// Owns the USB serial contract: framing with CRC16, JSON serialization of
// outbound traffic, and parsing of commands coming from the Raspberry Pi.
class SerialLink {
 public:
  using CommandCallback = void (*)(const InboundCommand& cmd);

  void begin(unsigned long baud);
  void setCommandCallback(CommandCallback callback) { callback_ = callback; }
  void poll();

  void sendHello();
  void sendTelemetry(const TelemetryData& telemetry);
  void sendPhotoChunk(const PhotoChunkData& chunk);
  void sendDeviceStatus(const DeviceStatus& status);
  void sendConfigAck(uint16_t version, uint8_t command, uint8_t status, const char* message = nullptr);
  void sendEvent(const char* severity, const char* code, const char* message);
  // Result of a set_actuator command, correlated by command_id. The Pi bridge
  // returns this to the API so the web UI gets a real device confirmation.
  void sendActuatorAck(const char* command_id, const char* actuator, bool state,
                       const char* status);

 private:
  void emit(JsonDocument& doc);
  void processLine(char* line);
  static uint8_t parseTarget(const char* value);

  CommandCallback callback_ = nullptr;
  char line_buffer_[GW_MAX_SERIAL_LINE];
  size_t line_length_ = 0;
  bool overflow_ = false;
  DynamicJsonDocument inbound_{GW_MAX_SERIAL_LINE};
  String outbound_;
};

extern SerialLink serialLink;
