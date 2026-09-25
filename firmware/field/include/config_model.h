#pragma once

#include <Arduino.h>

#include "config.h"

// Runtime control configuration, mirroring the JSON document the Raspberry Pi
// sends (hysteresis / irrigation / safety). It is persisted in NVS so the
// node keeps controlling the greenhouse across reboots and communication
// losses, which is the whole reason the automation lives on the field node.

#include <ArduinoJson.h>

struct HysteresisPair {
  float on = 0.0f;
  float off = 0.0f;
};

struct RuntimeConfig {
  uint16_t version = 0;
  char crop[24] = "tomate";

  // Temperature (fan): turn ON at/above `temp.on`, OFF at/below `temp.off`.
  HysteresisPair temp{30.0f, 27.5f};
  // Humidity (humidifier): turn ON at/below `humidity.on`, OFF at/above `off`.
  HysteresisPair humidity{60.0f, 68.0f};
  // Soil (pump): turn ON at/below `soil.on`, OFF at/above `off`.
  HysteresisPair soil{35.0f, 45.0f};

  bool irrigation_enabled = false;

  uint32_t max_on_fan_s = 7200;
  uint32_t max_on_humidifier_s = 7200;
  uint32_t max_on_pump_s = 900;

  // Parse the JSON config document. Returns false on malformed input.
  bool fromJson(const char* json, size_t length);
  bool fromJson(const String& json);
  bool fromJsonDocument(JsonVariantConst root);

  // Serialize for persistence/reporting.
  String toJson() const;

  bool valid() const;
};

// CRC16/CCITT-FALSE over the raw config bytes, matching the gateway commit.
uint16_t configCrc16(const char* data, size_t length);
