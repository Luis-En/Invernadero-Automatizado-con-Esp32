#include "usb_telemetry.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <math.h>
#include <time.h>

namespace {

float round1(float value) {
  if (isnan(value)) {
    return NAN;
  }
  return roundf(value * 10.0f) / 10.0f;
}

// A NaN or a literal 0 from the sensor layer both mean "no reading". Emitting
// null keeps the dashboard showing "no data" instead of a fake 0.
void writeNullable(JsonDocument& doc, const char* key, float value) {
  if (isnan(value) || value == 0.0f) {
    doc[key] = nullptr;
  } else {
    doc[key] = round1(value);
  }
}

void appendFramed(const char* payload, size_t length) {
  const uint16_t crc = crc16_ccitt((const uint8_t*)payload, length);
  Serial.write((const uint8_t*)payload, length);
  Serial.printf("*%04x\n", crc);
}

}  // namespace

namespace usb_telemetry {

void emit(const TelemetryData& telemetry) {
  StaticJsonDocument<1024> doc;
  doc["type"] = "telemetry";

  // Epoch 0 means the node has no wall clock yet (no time sync). Leave the
  // timestamp out and the bridge stamps the arrival time instead.
  if (telemetry.epoch > 0) {
    char timestamp[32];
    time_t epoch = (time_t)telemetry.epoch;
    struct tm utc;
    gmtime_r(&epoch, &utc);
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &utc);
    doc["timestamp"] = timestamp;
  }

  writeNullable(doc, "temperature", telemetry.temperature);
  writeNullable(doc, "humidity", telemetry.humidity);
  writeNullable(doc, "pressure", telemetry.pressure);

  JsonArray soil_adc = doc.createNestedArray("soil_adc");
  JsonArray soil_pct = doc.createNestedArray("soil_pct");
  JsonArray soil_ok = doc.createNestedArray("soil_ok");
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    soil_adc.add(telemetry.soil[i].adc);
    soil_pct.add(isnan(telemetry.soil[i].pct) ? 0.0f : round1(telemetry.soil[i].pct));
    soil_ok.add(telemetry.soil[i].ok);
  }

  doc["fan_1_state"] = telemetry.actuators[ACT_FAN_1];
  doc["fan_2_state"] = telemetry.actuators[ACT_FAN_2];
  doc["humidifier_1_state"] = telemetry.actuators[ACT_HUMIDIFIER_1];
  doc["humidifier_2_state"] = telemetry.actuators[ACT_HUMIDIFIER_2];
  doc["pump_state"] = telemetry.actuators[ACT_PUMP];
  doc["rssi"] = (int)telemetry.rssi;
  doc["device_id"] =
      telemetry.device_id[0] != '\0' ? telemetry.device_id : "field_esp32";
  doc["sequence"] = telemetry.sequence;

  char buffer[1024];
  const size_t written = serializeJson(doc, buffer, sizeof(buffer));
  if (written == 0 || written >= sizeof(buffer)) {
    Serial.println("# usb_telemetry: document did not fit");
    return;
  }
  appendFramed(buffer, written);
}

}  // namespace usb_telemetry
