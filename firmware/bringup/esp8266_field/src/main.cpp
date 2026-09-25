// ESP8266 field bring-up node: one soil moisture sensor on A0.
//
// Responsibilities:
//   * Sample A0 with a trimmed mean and convert to a percentage with a
//     two-point (dry/wet) calibration.
//   * Broadcast TelemetryMsg frames over ESP-NOW to the gateway.
//   * Print its own readings and calibration over USB serial so the sensor can
//     be verified with no gateway present.
//
// Serial commands (115200 baud, newline terminated):
//   cal dry   - capture the current raw value as the dry reference
//   cal wet   - capture the current raw value as the wet reference
//   show      - print the current calibration and last reading
//   reset     - restore the default calibration

#include <Arduino.h>

#include "espnow_hal.h"
#include "protocol.h"

#include "config.h"

namespace {

float soil_dry = SOIL_DRY_DEFAULT;
float soil_wet = SOIL_WET_DEFAULT;
uint16_t last_raw = 0;
uint8_t last_pct = 0;
uint16_t sequence = 0;
uint32_t boot_ms = 0;
uint32_t last_telemetry_ms = 0;
uint32_t last_hello_ms = 0;

char command_buffer[32];
size_t command_length = 0;

uint16_t readSoilRaw() {
  // Trimmed mean: drop the min and max, average the rest. Rejects a single
  // bad conversion without hiding a genuinely changing reading.
  uint32_t sum = 0;
  uint16_t min_value = 0xFFFF;
  uint16_t max_value = 0;
  for (uint8_t i = 0; i < SOIL_SAMPLES; i++) {
    uint16_t value = (uint16_t)analogRead(A0);
    sum += value;
    if (value < min_value) min_value = value;
    if (value > max_value) max_value = value;
    delayMicroseconds(300);
  }
  sum -= min_value;
  sum -= max_value;
  return (uint16_t)(sum / (SOIL_SAMPLES - 2));
}

uint8_t rawToPercent(uint16_t raw) {
  if (soil_dry <= soil_wet) {
    return 0;  // invalid calibration
  }
  float pct = ((float)soil_dry - (float)raw) / ((float)soil_dry - (float)soil_wet) * 100.0f;
  if (pct < 0.0f) pct = 0.0f;
  if (pct > 100.0f) pct = 100.0f;
  return (uint8_t)(pct + 0.5f);
}

void sampleSensor() {
  last_raw = readSoilRaw();
  last_pct = rawToPercent(last_raw);
}

void sendHello() {
  HelloMsg msg;
  memset(&msg, 0, sizeof(msg));
  msg.hdr.magic = ESPNOW_MAGIC;
  msg.hdr.version = ESPNOW_PROTO_VERSION;
  msg.hdr.type = MSG_HELLO;
  memcpy(msg.hdr.src, espNow.ownMac(), 6);
  msg.hdr.seq = espNow.nextSeq();
  msg.role = ROLE_FIELD;
  msg.fw_major = 0;
  msg.fw_minor = 1;
  msg.fw_patch = 0;
  msg.uptime_s = (millis() - boot_ms) / 1000UL;
  strncpy(msg.device_id, FIELD_DEVICE_ID, sizeof(msg.device_id) - 1);
  espNow.sendBroadcast((const uint8_t*)&msg, sizeof(msg));
}

void sendTelemetry() {
  // Only the first soil sensor is present on this bring-up board; the other
  // five are reported as invalid so the backend shows them as unavailable.
  TelemetryMsg msg;
  memset(&msg, 0, sizeof(msg));
  msg.hdr.magic = ESPNOW_MAGIC;
  msg.hdr.version = ESPNOW_PROTO_VERSION;
  msg.hdr.type = MSG_TELEMETRY;
  memcpy(msg.hdr.src, espNow.ownMac(), 6);
  msg.hdr.seq = espNow.nextSeq();
  msg.epoch = 0;
  msg.temperature_c_x100 = 0;  // no BME280 on this board
  msg.humidity_pct_x100 = 0;
  msg.pressure_hpa = 0;
  msg.soil_adc[0] = last_raw;
  msg.soil_pct[0] = last_pct;
  msg.soil_ok_mask = 0x01;  // only sensor A1 valid
  msg.actuator_mask = 0;
  msg.rssi = 0;
  espNow.sendBroadcast((const uint8_t*)&msg, sizeof(msg));
  sequence++;
}

void printReading() {
  Serial.printf("[field] raw=%u  soil=%u%%  cal(dry=%u wet=%u)  seq=%u\n",
                (unsigned)last_raw, (unsigned)last_pct,
                (unsigned)soil_dry, (unsigned)soil_wet, (unsigned)sequence);
}

void handleCommand(const char* command) {
  if (strcmp(command, "cal dry") == 0) {
    soil_dry = readSoilRaw();
    Serial.printf("[field] dry calibration set to raw=%u\n", (unsigned)soil_dry);
    sampleSensor();
  } else if (strcmp(command, "cal wet") == 0) {
    soil_wet = readSoilRaw();
    Serial.printf("[field] wet calibration set to raw=%u\n", (unsigned)soil_wet);
    sampleSensor();
  } else if (strcmp(command, "show") == 0) {
    printReading();
  } else if (strcmp(command, "reset") == 0) {
    soil_dry = SOIL_DRY_DEFAULT;
    soil_wet = SOIL_WET_DEFAULT;
    Serial.println("[field] calibration reset to defaults");
    sampleSensor();
  } else if (strlen(command) > 0) {
    Serial.printf("[field] unknown command: %s\n", command);
    Serial.println("[field] commands: cal dry | cal wet | show | reset");
  }
}

void pollSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (command_length > 0) {
        command_buffer[command_length] = '\0';
        handleCommand(command_buffer);
        command_length = 0;
      }
    } else if (command_length < sizeof(command_buffer) - 1) {
      command_buffer[command_length++] = c;
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);
  boot_ms = millis();

  Serial.println();
  Serial.printf("[field] ESP8266 field bring-up %s\n", FIELD_FW_VERSION);
  Serial.println("[field] commands: cal dry | cal wet | show | reset");

  if (!espNow.begin(ESPNOW_CHANNEL_DEFAULT)) {
    Serial.println("[field] ESP-NOW init FAILED");
  } else {
    Serial.print("[field] ESP-NOW ready, MAC=");
    const uint8_t* mac = espNow.ownMac();
    Serial.printf("%02X:%02X:%02X:%02X:%02X:%02X\n",
                  mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  }

  sampleSensor();
  printReading();
  sendHello();
  last_hello_ms = millis();
}

void loop() {
  pollSerial();

  const uint32_t now = millis();

  if (now - last_telemetry_ms >= TELEMETRY_INTERVAL_MS) {
    last_telemetry_ms = now;
    sampleSensor();
    sendTelemetry();
    printReading();
  }

  if (now - last_hello_ms >= HELLO_INTERVAL_MS) {
    last_hello_ms = now;
    sendHello();
  }

  delay(2);
}
