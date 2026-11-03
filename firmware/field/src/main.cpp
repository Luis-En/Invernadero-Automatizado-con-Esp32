#include <Arduino.h>
#include <ctype.h>

#include "actuators.h"
#include "automation.h"
#include "config.h"
#include "config_model.h"
#include "espnow_hal.h"
#include "field_link.h"
#include "persistence.h"
#include "protocol.h"
#include "sensors.h"
#include "mqtt_link.h"
#include "usb_telemetry.h"
#include "wifi_photo.h"

namespace {

RuntimeConfig runtime_config;
ActuatorState actuator_state;
SensorSnapshot latest_snapshot;

uint32_t boot_ms = 0;
uint32_t last_sample_ms = 0;
uint32_t last_telemetry_ms = 0;
uint32_t last_hello_ms = 0;

bool mqtt_active[ACT_COUNT] = {};
bool mqtt_values[ACT_COUNT] = {};
uint32_t mqtt_on_since[ACT_COUNT] = {};

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
    mqtt_active[i] = false;
  }
}

void applyManualOverride(const bool values[ACT_COUNT]) {
  manual_override_active = true;
  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    manual_values[i] = values[i];
  }
}

void runControlCycle(uint32_t now_ms) {
#if FIELD_HAS_ACTUATORS
  computeActuatorStates(runtime_config, latest_snapshot, actuator_state, now_ms,
                        manual_override_active, manual_values);
  // MQTT overrides only the selected output, with local irrigation interlock
  // and continuous-ON limits. A config change clears these manual overrides.
  for (uint8_t i = 0; i < ACT_COUNT; ++i) {
    if (!mqtt_active[i]) continue;
    const uint32_t limit = i == ACT_PUMP ? runtime_config.max_on_pump_s
        : (i <= ACT_FAN_2 ? runtime_config.max_on_fan_s : runtime_config.max_on_humidifier_s);
    if ((i == ACT_PUMP && !runtime_config.irrigation_enabled) ||
        (mqtt_values[i] && limit && now_ms - mqtt_on_since[i] >= limit * 1000UL)) {
      mqtt_values[i] = false;
    }
    actuator_state.set(i, mqtt_values[i]);
  }
  actuators.apply(actuator_state);
  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    last_outputs[i] = actuators.outputState(i);
  }
#else
  (void)now_ms;
#endif
}

bool applyMqttCommand(uint8_t index, bool state) {
  if (index >= ACT_COUNT || (index == ACT_PUMP && state && !runtime_config.irrigation_enabled)) return false;
  if (state && (!mqtt_active[index] || !mqtt_values[index])) mqtt_on_since[index] = millis();
  mqtt_active[index] = true;
  mqtt_values[index] = state;
  runControlCycle(millis());
  // Request fresh telemetry on the next loop, in addition to the direct ACK.
  last_telemetry_ms = millis() - FIELD_TELEMETRY_INTERVAL_MS;
  return actuators.outputState(index) == state;
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

// -----------------------------------------------------------------------------
// Serial calibration commands (USB serial, 115200):
//   CAL SHOW        print each slot's dry/wet ADC
//   CAL DRY <slot>  capture the current ADC as the dry point
//   CAL WET <slot>  capture the current ADC as the wet point
//   CAL SAVE        persist all slots to NVS
//   CAL RESET       restore the 3.3 V defaults (then CAL SAVE)
// Slots are A1,A2,A3,B1,B2,B3 = 0..5. Only the slots in FIELD_SOIL_MASK are
// sampled in telemetry; calibration works on any slot.
void printCalibration() {
  static const char* const labels[SOIL_SENSOR_COUNT] = {"A1", "A2", "A3",
                                                        "B1", "B2", "B3"};
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    const SensorManager::Calibration& cal = sensors.calibration(i);
    Serial.printf("[cal] %s dry=%u wet=%u\n", labels[i], cal.dry_adc, cal.wet_adc);
  }
}

void handleCalibrationLine(char* line) {
  for (char* p = line; *p != '\0'; p++) {
    *p = (char)toupper((unsigned char)*p);
  }

  if (strncmp(line, "CAL SHOW", 8) == 0) {
    printCalibration();
    return;
  }
  if (strncmp(line, "CAL SAVE", 8) == 0) {
    sensors.saveCalibration();
    Serial.println("[cal] saved to NVS");
    return;
  }
  if (strncmp(line, "CAL RESET", 9) == 0) {
    sensors.resetCalibration();
    Serial.println("[cal] reset to 3.3 V defaults (run CAL SAVE to persist)");
    return;
  }

  int slot = -1;
  if (sscanf(line, "CAL DRY %d", &slot) == 1) {
    if (slot < 0 || slot >= SOIL_SENSOR_COUNT) {
      Serial.println("[cal] slot must be 0..5");
      return;
    }
    uint16_t adc = sensors.sampleRaw((uint8_t)slot);
    sensors.setCalibration((uint8_t)slot, adc, sensors.calibration((uint8_t)slot).wet_adc);
    Serial.printf("[cal] slot %d dry=%u\n", slot, adc);
    return;
  }
  if (sscanf(line, "CAL WET %d", &slot) == 1) {
    if (slot < 0 || slot >= SOIL_SENSOR_COUNT) {
      Serial.println("[cal] slot must be 0..5");
      return;
    }
    uint16_t adc = sensors.sampleRaw((uint8_t)slot);
    sensors.setCalibration((uint8_t)slot, sensors.calibration((uint8_t)slot).dry_adc, adc);
    Serial.printf("[cal] slot %d wet=%u\n", slot, adc);
    return;
  }

  Serial.println("[cal] CAL SHOW | CAL DRY <0-5> | CAL WET <0-5> | CAL SAVE | CAL RESET");
}

void pollCalibrationCommands() {
  static char line[64];
  static size_t length = 0;
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (length > 0) {
        line[length] = '\0';
        handleCalibrationLine(line);
        length = 0;
      }
    } else if (length < sizeof(line) - 1) {
      line[length++] = c;
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  boot_ms = millis();

  // Safety first: every output OFF before anything else can fail.
#if FIELD_HAS_ACTUATORS
  actuators.begin();
  actuators.allOff();
#endif

  persistence.begin();
  sensors.begin();

  runtime_config = RuntimeConfig();
  if (persistence.loadConfig(runtime_config)) {
    Serial.printf("[field] loaded config v%u from NVS\n", runtime_config.version);
  } else {
    Serial.println("[field] no stored config, using safe defaults (irrigation off)");
    runtime_config.irrigation_enabled = false;
  }

#if !FIELD_CALIBRATION_ONLY
  fieldLink.begin(applyNewConfig);
  fieldLink.setManualOverrideCallback(applyManualOverride);

#if FIELD_HAS_CAMERA_AP
  // The camera joins the AP this node raises, so the AP must be up first; it
  // also fixes the Wi-Fi channel ESP-NOW then uses.
  wifiPhoto.begin();
#endif

  constexpr uint8_t kEspNowMode =
#if FIELD_HAS_CAMERA_AP
      EspNowHal::MODE_KEEP_APSTA;
#else
      EspNowHal::MODE_KEEP_STA;
#endif

  if (!espNow.begin(FIELD_ESPNOW_CHANNEL, kEspNowMode)) {
    Serial.println("[field] ESP-NOW init failed");
  }
#endif

#if !FIELD_CALIBRATION_ONLY
  mqttBegin(applyMqttCommand);
#endif

  // Prime the snapshot so the first control cycle has data.
  sensors.read(latest_snapshot);
  runControlCycle(millis());
  printStatus(latest_snapshot, last_outputs);

#if !FIELD_CALIBRATION_ONLY
  fieldLink.sendHello(millis());
  last_hello_ms = millis();
#endif
}

void loop() {
  const uint32_t now_ms = millis();

  // 0. Serial calibration commands (CAL ...).
  pollCalibrationCommands();

#if !FIELD_CALIBRATION_ONLY
  // 1. Inbound commands / config pushes.
  fieldLink.poll(now_ms);
  mqttPoll(now_ms);

#if FIELD_HAS_CAMERA_AP
  // 2. Serve the camera's Wi-Fi photo uploads and forward them to the gateway.
  wifiPhoto.poll();
#endif
#endif

  // 3. Sample sensors on their interval.
  if (now_ms - last_sample_ms >= FIELD_SAMPLE_INTERVAL_MS) {
    last_sample_ms = now_ms;
    sensors.read(latest_snapshot);
    runControlCycle(now_ms);
    printStatus(latest_snapshot, last_outputs);
  }

#if !FIELD_CALIBRATION_ONLY
  // 4. Publish telemetry. When the link is down this simply fails silently;
  //    the node keeps controlling the greenhouse with the stored config.
  if (now_ms - last_telemetry_ms >= FIELD_TELEMETRY_INTERVAL_MS) {
    last_telemetry_ms = now_ms;
    TelemetryData telemetry = buildTelemetry(now_ms);
    fieldLink.sendTelemetry(telemetry);
    // Also publish on USB so the Pi bridge can read the field node directly,
    // with or without a gateway in between.
    usb_telemetry::emit(telemetry);
  }

  // 5. Announce presence so the gateway can discover/route to us.
  if (now_ms - last_hello_ms >= FIELD_HELLO_INTERVAL_MS) {
    last_hello_ms = now_ms;
    fieldLink.sendHello(now_ms);
  }
#endif

  delay(2);
}
