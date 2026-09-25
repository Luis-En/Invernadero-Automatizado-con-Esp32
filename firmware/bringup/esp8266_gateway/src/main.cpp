// ESP8266 gateway bring-up node: ESP-NOW -> USB serial JSON.
//
// Every ESP-NOW frame from the field node is decoded and emitted to the serial
// port as:
//     <json>*<CRC16 hex>\n
// CRC16 is CRC-16/CCITT-FALSE over the JSON bytes, matching the Raspberry Pi
// serial bridge (backend/serial_bridge/gateway_protocol.py). This lets the PC
// verify the whole field -> gateway -> backend path with real hardware.
//
// Every line is valid CRC-framed JSON, including diagnostics, which are sent
// as {"type":"log",...} so the bridge never logs a parse warning.

#include <Arduino.h>
#include <ArduinoJson.h>

#include "espnow_hal.h"
#include "protocol.h"

#include "config.h"

namespace {

uint32_t boot_ms = 0;
uint32_t last_status_ms = 0;
uint32_t telemetry_count = 0;
uint32_t ack_count = 0;
uint32_t dropped_count = 0;

void emitJson(const JsonDocument& doc) {
  static char buffer[SERIAL_LINE_MAX];
  size_t length = serializeJson(doc, buffer, sizeof(buffer));
  if (length == 0) {
    return;
  }
  Serial.print(buffer);
  Serial.print('*');
  Serial.printf("%04X\n", crc16_ccitt((const uint8_t*)buffer, length));
}

void emitLog(const char* message) {
  StaticJsonDocument<192> doc;
  doc["type"] = "log";
  doc["device_id"] = GW_DEVICE_ID;
  doc["message"] = message;
  doc["uptime_s"] = (millis() - boot_ms) / 1000UL;
  emitJson(doc);
}

void handleTelemetry(const EspNowMessage& frame) {
  TelemetryMsg msg;
  memcpy(&msg, frame.data, sizeof(msg));

  StaticJsonDocument<1024> doc;
  doc["type"] = "telemetry";
  doc["device_id"] = FIELD_DEVICE_ID_DEFAULT;
  doc["sequence"] = msg.hdr.seq;
  doc["timestamp_ms"] = millis();

  // Only report the sensors this bring-up build actually has.
  doc["temperature"] = (float)msg.temperature_c_x100 / 100.0f;
  doc["humidity"] = (float)msg.humidity_pct_x100 / 100.0f;
  doc["pressure"] = (float)msg.pressure_hpa;

  JsonArray soil_adc = doc.createNestedArray("soil_adc");
  JsonArray soil_pct = doc.createNestedArray("soil_pct");
  JsonArray soil_ok = doc.createNestedArray("soil_ok");
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    soil_adc.add(msg.soil_adc[i]);
    soil_pct.add(msg.soil_pct[i]);
    soil_ok.add(((msg.soil_ok_mask >> i) & 0x01) != 0);
  }

  doc["fan_1_state"] = false;
  doc["fan_2_state"] = false;
  doc["humidifier_1_state"] = false;
  doc["humidifier_2_state"] = false;
  doc["pump_state"] = false;
  doc["rssi"] = frame.rssi;

  emitJson(doc);
  telemetry_count++;

  char line[80];
  snprintf(line, sizeof(line), "telemetry seq=%u rssi=%d soil0=%u%%",
           (unsigned)msg.hdr.seq, (int)frame.rssi, (unsigned)msg.soil_pct[0]);
  emitLog(line);
}

void handleHello(const EspNowMessage& frame) {
  HelloMsg msg;
  memcpy(&msg, frame.data, sizeof(msg));
  char device_id[17];
  memcpy(device_id, msg.device_id, sizeof(msg.device_id));
  device_id[sizeof(msg.device_id)] = '\0';

  StaticJsonDocument<256> doc;
  doc["type"] = "hello";
  doc["device_id"] = device_id;
  doc["role"] = msg.role;
  doc["firmware"] = String(msg.fw_major) + "." + String(msg.fw_minor) + "." + String(msg.fw_patch);
  doc["uptime_s"] = msg.uptime_s;
  doc["rssi"] = frame.rssi;
  emitJson(doc);
}

void handleAck(const EspNowMessage& frame) {
  AckMsg msg;
  memcpy(&msg, frame.data, sizeof(msg));
  ack_count++;
  char line[64];
  snprintf(line, sizeof(line), "ack cmd=%u status=%u version=%u",
           (unsigned)msg.cmd, (unsigned)msg.status, (unsigned)msg.version);
  emitLog(line);
}

void handleFrame(const EspNowMessage& frame) {
  if (frame.length < sizeof(EspNowHeader)) {
    return;
  }
  EspNowHeader header;
  memcpy(&header, frame.data, sizeof(header));
  if (header.magic != ESPNOW_MAGIC || header.version != ESPNOW_PROTO_VERSION) {
    dropped_count++;
    return;
  }

  switch (header.type) {
    case MSG_TELEMETRY:
      if (frame.length >= sizeof(TelemetryMsg)) {
        handleTelemetry(frame);
      }
      break;
    case MSG_HELLO:
      if (frame.length >= sizeof(HelloMsg)) {
        handleHello(frame);
      }
      break;
    case MSG_ACK:
      if (frame.length >= sizeof(AckMsg)) {
        handleAck(frame);
      }
      break;
    default:
      break;
  }
}

void sendStatus() {
  StaticJsonDocument<256> doc;
  doc["type"] = "device_status";
  doc["device_id"] = GW_DEVICE_ID;
  doc["uptime_s"] = (millis() - boot_ms) / 1000UL;
  doc["telemetry_count"] = telemetry_count;
  doc["ack_count"] = ack_count;
  doc["dropped_count"] = dropped_count;
  doc["free_heap"] = ESP.getFreeHeap();
  emitJson(doc);
}

}  // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(300);
  boot_ms = millis();

  emitLog("ESP8266 gateway bring-up " GW_FW_VERSION);

  if (!espNow.begin(ESPNOW_CHANNEL_DEFAULT)) {
    emitLog("ESP-NOW init FAILED");
  } else {
    const uint8_t* mac = espNow.ownMac();
    char line[80];
    snprintf(line, sizeof(line), "ESP-NOW ready MAC=%02X:%02X:%02X:%02X:%02X:%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    emitLog(line);
  }
}

void loop() {
  EspNowMessage frame;
  while (espNow.poll(frame, 0)) {
    handleFrame(frame);
  }

  const uint32_t now = millis();
  if (now - last_status_ms >= 30000UL) {
    last_status_ms = now;
    sendStatus();
  }

  delay(2);
}
