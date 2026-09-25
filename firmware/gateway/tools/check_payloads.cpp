// Host harness: builds the exact telemetry and photo_chunk documents the
// gateway emits, using the same json_builder.cpp and protocol.cpp that the
// ESP32 and ESP8266 firmwares compile. Run through scripts/check_payloads.sh,
// which validates the output against the backend schema.
#include <cstdio>
#include <cstring>
#include <string>

#include <ArduinoJson.h>

#include "json_builder.h"
#include "protocol.h"

int main() {
  TelemetryData telemetry;
  memset(&telemetry, 0, sizeof(telemetry));
  telemetry.temperature = 26.53f;
  telemetry.humidity = 72.04f;
  telemetry.pressure = 1013.2f;

  const uint16_t adc[SOIL_SENSOR_COUNT] = {2252, 2374, 2129, 2457, 2293, 2539};
  const float pct[SOIL_SENSOR_COUNT] = {45.0f, 42.0f, 48.0f, 40.0f, 44.0f, 38.0f};
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    telemetry.soil[i].adc = adc[i];
    telemetry.soil[i].pct = pct[i];
    telemetry.soil[i].ok = true;
  }
  telemetry.actuators[ACT_FAN_1] = true;
  telemetry.actuators[ACT_FAN_2] = true;
  telemetry.actuators[ACT_PUMP] = false;
  telemetry.rssi = -63;
  strcpy(telemetry.device_id, "field_esp32");
  telemetry.sequence = 7;

  DynamicJsonDocument telemetryDoc(json_builder::kTelemetryCapacity);
  json_builder::telemetry(telemetryDoc, telemetry, "2026-09-21T15:30:00Z");
  if (telemetryDoc.overflowed() || !telemetryDoc.containsKey("device_id") ||
      !telemetryDoc.containsKey("sequence")) {
    fprintf(stderr, "telemetry document overflowed or lost keys\n");
    return 1;
  }
  std::string telemetryLine;
  serializeJson(telemetryDoc, telemetryLine);
  printf("%s\n", telemetryLine.c_str());

  PhotoChunkData chunk;
  memset(&chunk, 0, sizeof(chunk));
  chunk.sequence = 7;
  chunk.total_chunks = 21;
  chunk.chunk_index = 3;
  chunk.crc16 = 0xABCD;
  chunk.length = 200;
  for (uint16_t i = 0; i < chunk.length; i++) {
    chunk.data[i] = (uint8_t)i;
  }
  strcpy(chunk.device_id, "camera");

  DynamicJsonDocument photoDoc(json_builder::kPhotoChunkCapacity);
  json_builder::photoChunk(photoDoc, chunk);
  if (photoDoc.overflowed() || !photoDoc.containsKey("data")) {
    fprintf(stderr, "photo chunk document overflowed or lost keys\n");
    return 1;
  }
  std::string photoLine;
  serializeJson(photoDoc, photoLine);
  printf("%s\n", photoLine.c_str());
  return 0;
}
