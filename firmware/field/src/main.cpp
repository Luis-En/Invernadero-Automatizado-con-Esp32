#include <Arduino.h>

#include "actuators.h"
#include "automation.h"
#include "config.h"
#include "config_model.h"
#include "espnow_hal.h"
#include "field_link.h"
#include "persistence.h"
#include "protocol.h"
#include "sensors.h"
#include "wifi_photo.h"

namespace {

RuntimeConfig runtime_config;
ActuatorState actuator_state;
SensorSnapshot latest_snapshot;

uint32_t boot_ms = 0;
uint32_t last_sample_ms = 0;
uint32_t last_telemetry_ms = 0;
uint32_t last_hello_ms = 0;

bool manual_override_active = false;
bool manual_values[ACT_COUNT] = {false, false, false, false, false};

// Last valid actuator mask, used by telemetry.
bool last_outputs[ACT_COUNT] = {false, false, false, false, false};

void applyNewConfig(const RuntimeConfig& config) {
  runtime_config = config;
  persistence.saveConfig(config);
  // Never carry a manual override across a config change: the new limits and
  // hysteresis take over immediately.
  manual_override_active = false;
  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    manual_values[i] = false;
  }
}

void applyManualOverride(const bool values[ACT_COUNT]) {
  manual_override_active = true;
  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    manual_values[i] = values[i];
  }
}

void runControlCycle(uint32_t now_ms) {
  computeActuatorStates(runtime_config, latest_snapshot, actuator_state, now_ms,
                        manual_override_active, manual_values);
  actuators.apply(actuator_state);
  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    last_outputs[i] = actuators.outputState(i);
  }
}

TelemetryData buildTelemetry(uint32_t now_ms) {
  TelemetryData telemetry;
  memset(&telemetry, 0, sizeof(telemetry));
  telemetry.epoch = fieldLink.epochNow();
  telemetry.temperature = latest_snapshot.temperature;
  telemetry.humidity = latest_snapshot.humidity;
  telemetry.pressure = latest_snapshot.pressure;
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    telemetry.soil[i] = {latest_snapshot.soil[i].adc,
                         latest_snapshot.soil[i].pct,
                         latest_snapshot.soil[i].ok};
  }
  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    telemetry.actuators[i] = last_outputs[i];
  }
  telemetry.rssi = 0;
  strncpy(telemetry.device_id, FIELD_DEVICE_ID, sizeof(telemetry.device_id) - 1);
  telemetry.sequence = (uint16_t)(now_ms / FIELD_TELEMETRY_INTERVAL_MS);
  (void)now_ms;
  return telemetry;
}

void printStatus(const SensorSnapshot& snapshot, const bool outputs[ACT_COUNT]) {
  static const char* const kSoilLabels[SOIL_SENSOR_COUNT] = {"A1", "A2", "A3",
                                                             "B1", "B2", "B3"};
  char soil[96];
  int written = 0;
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    if (snapshot.soil[i].ok) {
      written += snprintf(soil + written, sizeof(soil) - written, "%s=%u/%d%% ",
                          kSoilLabels[i], snapshot.soil[i].adc,
                          (int)lroundf(snapshot.soil[i].pct));
    } else {
      written += snprintf(soil + written, sizeof(soil) - written, "%s=-- ",
                          kSoilLabels[i]);
    }
  }
  Serial.printf("[field] T=%.1fC H=%.1f%% P=%.1fhPa | %s| avg=%.1f%%\n",
                snapshot.temperature, snapshot.humidity, snapshot.pressure, soil,
                snapshot.soil_average);
  Serial.printf("[field] out fan1=%d fan2=%d hum1=%d hum2=%d pump=%d%s\n",
                outputs[ACT_FAN_1], outputs[ACT_FAN_2], outputs[ACT_HUMIDIFIER_1],
                outputs[ACT_HUMIDIFIER_2], outputs[ACT_PUMP],
                manual_override_active ? " (manual)" : "");
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  boot_ms = millis();

  // Safety first: every output OFF before anything else can fail.
  actuators.begin();
  actuators.allOff();

  persistence.begin();
  sensors.begin();

  runtime_config = RuntimeConfig();
  if (persistence.loadConfig(runtime_config)) {
    Serial.printf("[field] loaded config v%u from NVS\n", runtime_config.version);
  } else {
    Serial.println("[field] no stored config, using safe defaults (irrigation off)");
    runtime_config.irrigation_enabled = false;
  }

  fieldLink.begin(applyNewConfig);
  fieldLink.setManualOverrideCallback(applyManualOverride);

  // The camera joins the AP this node raises, so the AP must be up first; it
  // also fixes the Wi-Fi channel ESP-NOW then uses.
  wifiPhoto.begin();

  if (!espNow.begin(FIELD_ESPNOW_CHANNEL, EspNowHal::MODE_KEEP_APSTA)) {
    Serial.println("[field] ESP-NOW init failed");
  }

  // Prime the snapshot so the first control cycle has data.
  sensors.read(latest_snapshot);
  runControlCycle(millis());
  printStatus(latest_snapshot, last_outputs);

  fieldLink.sendHello(millis());
  last_hello_ms = millis();
}

void loop() {
  const uint32_t now_ms = millis();

  // 1. Inbound commands / config pushes.
  fieldLink.poll(now_ms);

  // 2. Serve the camera's Wi-Fi photo uploads and forward them to the gateway.
  wifiPhoto.poll();

  // 3. Sample sensors on their interval.
  if (now_ms - last_sample_ms >= FIELD_SAMPLE_INTERVAL_MS) {
    last_sample_ms = now_ms;
    sensors.read(latest_snapshot);
    runControlCycle(now_ms);
    printStatus(latest_snapshot, last_outputs);
  }

  // 4. Publish telemetry. When the link is down this simply fails silently;
  //    the node keeps controlling the greenhouse with the stored config.
  if (now_ms - last_telemetry_ms >= FIELD_TELEMETRY_INTERVAL_MS) {
    last_telemetry_ms = now_ms;
    TelemetryData telemetry = buildTelemetry(now_ms);
    fieldLink.sendTelemetry(telemetry);
  }

  // 5. Announce presence so the gateway can discover/route to us.
  if (now_ms - last_hello_ms >= FIELD_HELLO_INTERVAL_MS) {
    last_hello_ms = now_ms;
    fieldLink.sendHello(now_ms);
  }

  delay(2);
}
