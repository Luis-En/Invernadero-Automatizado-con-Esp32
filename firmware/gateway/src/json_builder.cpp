#include "json_builder.h"

#include <math.h>

namespace {
const char* kDeviceIdField = "field_esp32";
const char* kDeviceIdCamera = "camera";
const char* kHexDigits = "0123456789abcdef";

float round1(float value) {
  return roundf(value * 10.0f) / 10.0f;
}
}  // namespace

namespace json_builder {

void telemetry(JsonDocument& doc, const TelemetryData& telemetry, const char* timestamp) {
  doc["type"] = "telemetry";
  doc["timestamp"] = timestamp;

  // A value of exactly 0 is the on-wire sentinel for "no reading" (the field
  // node has no BME280, or it failed). Emit null so the dashboard shows "no
  // data" instead of a fake 0 C / 0 %.
  if (telemetry.temperature == 0.0f) {
    doc["temperature"] = nullptr;
  } else {
    doc["temperature"] = round1(telemetry.temperature);
  }
  if (telemetry.humidity == 0.0f) {
    doc["humidity"] = nullptr;
  } else {
    doc["humidity"] = round1(telemetry.humidity);
  }
  if (telemetry.pressure == 0.0f) {
    doc["pressure"] = nullptr;
  } else {
    doc["pressure"] = round1(telemetry.pressure);
  }

  JsonArray soilAdc = doc.createNestedArray("soil_adc");
  JsonArray soilPct = doc.createNestedArray("soil_pct");
  JsonArray soilOk = doc.createNestedArray("soil_ok");
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    soilAdc.add(telemetry.soil[i].adc);
    soilPct.add(round1(telemetry.soil[i].pct));
    soilOk.add(telemetry.soil[i].ok);
  }

  doc["fan_1_state"] = telemetry.actuators[ACT_FAN_1];
  doc["fan_2_state"] = telemetry.actuators[ACT_FAN_2];
  doc["humidifier_1_state"] = telemetry.actuators[ACT_HUMIDIFIER_1];
  doc["humidifier_2_state"] = telemetry.actuators[ACT_HUMIDIFIER_2];
  doc["pump_state"] = telemetry.actuators[ACT_PUMP];
  doc["rssi"] = (int)telemetry.rssi;
  doc["device_id"] = telemetry.device_id[0] != '\0' ? telemetry.device_id : kDeviceIdField;
  doc["sequence"] = telemetry.sequence;
}

void photoChunk(JsonDocument& doc, const PhotoChunkData& chunk) {
  char hex[ESPNOW_PHOTO_DATA_MAX * 2 + 1];
  for (uint16_t i = 0; i < chunk.length; i++) {
    hex[i * 2] = kHexDigits[(chunk.data[i] >> 4) & 0x0F];
    hex[i * 2 + 1] = kHexDigits[chunk.data[i] & 0x0F];
  }
  hex[chunk.length * 2] = '\0';

  doc["type"] = "photo_chunk";
  doc["sequence"] = chunk.sequence;
  doc["total_chunks"] = chunk.total_chunks;
  doc["chunk_index"] = chunk.chunk_index;
  doc["crc16"] = chunk.crc16;
  doc["data"] = hex;
  doc["device_id"] = chunk.device_id[0] != '\0' ? chunk.device_id : kDeviceIdCamera;
}

void deviceStatus(JsonDocument& doc, const DeviceStatus& status, const char* timestamp) {
  doc["type"] = "device_status";
  doc["timestamp"] = timestamp;
  doc["gateway_online"] = true;
  doc["field_online"] = status.field_online;
  doc["camera_online"] = status.camera_online;

  if (status.field_rssi != 0) {
    doc["field_rssi"] = (int)status.field_rssi;
  } else {
    doc["field_rssi"] = nullptr;
  }
  if (status.camera_rssi != 0) {
    doc["camera_rssi"] = (int)status.camera_rssi;
  } else {
    doc["camera_rssi"] = nullptr;
  }

  if (status.field_last_seen_s == UINT32_MAX) {
    doc["field_last_seen_s"] = nullptr;
  } else {
    doc["field_last_seen_s"] = status.field_last_seen_s;
  }
  if (status.camera_last_seen_s == UINT32_MAX) {
    doc["camera_last_seen_s"] = nullptr;
  } else {
    doc["camera_last_seen_s"] = status.camera_last_seen_s;
  }

  doc["config_version"] = status.config_version;
  doc["uptime_s"] = status.uptime_s;
  doc["free_heap"] = status.free_heap;
  doc["simulate"] = status.simulate;
}

void configAck(JsonDocument& doc, uint16_t version, uint8_t command, uint8_t status,
               const char* message, const char* timestamp) {
  doc["type"] = "config_ack";
  doc["timestamp"] = timestamp;
  doc["version"] = version;
  doc["cmd"] = (int)command;
  doc["status"] = status == 0 ? "ok" : "error";
  if (message != nullptr) {
    doc["message"] = message;
  }
}

void event(JsonDocument& doc, const char* severity, const char* code, const char* message,
           const char* timestamp) {
  doc["type"] = "event";
  doc["timestamp"] = timestamp;
  doc["severity"] = severity;
  doc["code"] = code;
  doc["message"] = message;
}

void hello(JsonDocument& doc, const char* deviceId, const char* firmware, uint8_t protocolVersion,
           uint32_t uptimeSeconds, uint16_t configVersion, bool timeSynced, bool simulate,
           const char* timestamp) {
  doc["type"] = "hello";
  doc["timestamp"] = timestamp;
  doc["role"] = "gateway";
  doc["device_id"] = deviceId;
  doc["firmware"] = firmware;
  doc["protocol"] = (int)protocolVersion;
  doc["uptime_s"] = uptimeSeconds;
  doc["config_version"] = configVersion;
  doc["time_synced"] = timeSynced;
  doc["simulate"] = simulate;
}

}  // namespace json_builder
