#pragma once

#include <stdint.h>

#include <ArduinoJson.h>

#include "protocol.h"

// Builds the JSON documents the gateway emits over serial. These functions are
// deliberately free of Arduino and Serial dependencies so the exact payloads
// can be exercised on a host, and so ESP32 and ESP8266 share one definition.
namespace json_builder {

// Document capacities, measured from the payloads plus headroom. Keeping them
// here lets the host test use the same sizes as the firmware; a capacity that
// is too small makes ArduinoJson silently drop keys.
constexpr size_t kTelemetryCapacity = 1536;
constexpr size_t kPhotoChunkCapacity = 896;
constexpr size_t kDeviceStatusCapacity = 640;
constexpr size_t kHelloCapacity = 448;
constexpr size_t kConfigAckCapacity = 320;
constexpr size_t kEventCapacity = 320;

void telemetry(JsonDocument& doc, const TelemetryData& telemetry, const char* timestamp);
void photoChunk(JsonDocument& doc, const PhotoChunkData& chunk);
void deviceStatus(JsonDocument& doc, const DeviceStatus& status, const char* timestamp);
void configAck(JsonDocument& doc, uint16_t version, uint8_t command, uint8_t status,
               const char* message, const char* timestamp);
void event(JsonDocument& doc, const char* severity, const char* code, const char* message,
           const char* timestamp);
void hello(JsonDocument& doc, const char* deviceId, const char* firmware, uint8_t protocolVersion,
           uint32_t uptimeSeconds, uint16_t configVersion, bool timeSynced, bool simulate,
           const char* timestamp);

}  // namespace json_builder
