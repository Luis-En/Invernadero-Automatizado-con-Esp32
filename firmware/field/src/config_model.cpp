#include "config_model.h"

#include <ArduinoJson.h>

#include "protocol.h"

uint16_t configCrc16(const char* data, size_t length) {
  return crc16_ccitt((const uint8_t*)data, length);
}

static float readFloat(JsonVariantConst value, float fallback) {
  if (value.is<float>() || value.is<int>() || value.is<long>()) {
    return value.as<float>();
  }
  return fallback;
}

static uint32_t readSeconds(JsonVariantConst value, uint32_t fallback) {
  if (value.is<unsigned long>() || value.is<long>() || value.is<int>()) {
    return value.as<uint32_t>();
  }
  return fallback;
}

bool RuntimeConfig::fromJson(const char* json, size_t length) {
  StaticJsonDocument<1024> doc;
  DeserializationError error = deserializeJson(doc, json, length);
  if (error) {
    return false;
  }
  return fromJsonDocument(doc.as<JsonVariantConst>());
}

bool RuntimeConfig::fromJson(const String& json) {
  return fromJson(json.c_str(), json.length());
}

bool RuntimeConfig::fromJsonDocument(JsonVariantConst root) {
  RuntimeConfig next = *this;

  JsonVariantConst version = root["version"];
  if (version.is<unsigned int>() || version.is<int>()) {
    next.version = (uint16_t)version.as<unsigned int>();
  }

  const char* crop = root["crop"] | (const char*)nullptr;
  if (crop != nullptr) {
    strncpy(next.crop, crop, sizeof(next.crop) - 1);
    next.crop[sizeof(next.crop) - 1] = '\0';
  }

  JsonVariantConst hysteresis = root["hysteresis"];
  if (!hysteresis.isNull()) {
    JsonVariantConst temp = hysteresis["temp"];
    if (!temp.isNull()) {
      next.temp.on = readFloat(temp["on_above"], next.temp.on);
      next.temp.off = readFloat(temp["off_below"], next.temp.off);
    }
    JsonVariantConst humidity = hysteresis["humidity"];
    if (!humidity.isNull()) {
      next.humidity.on = readFloat(humidity["on_below"], next.humidity.on);
      next.humidity.off = readFloat(humidity["off_above"], next.humidity.off);
    }
    JsonVariantConst soil = hysteresis["soil"];
    if (!soil.isNull()) {
      next.soil.on = readFloat(soil["on_below_pct"], next.soil.on);
      next.soil.off = readFloat(soil["off_above_pct"], next.soil.off);
    }
  }

  JsonVariantConst irrigation = root["irrigation"];
  if (!irrigation.isNull()) {
    next.irrigation_enabled = irrigation["enabled"] | false;
  }

  JsonVariantConst safety = root["safety"]["max_on_seconds"];
  if (!safety.isNull()) {
    next.max_on_fan_s = readSeconds(safety["fan"], next.max_on_fan_s);
    next.max_on_humidifier_s = readSeconds(safety["humidifier"], next.max_on_humidifier_s);
    next.max_on_pump_s = readSeconds(safety["pump"], next.max_on_pump_s);
  }

  if (!next.valid()) {
    return false;
  }
  *this = next;
  return true;
}

bool RuntimeConfig::valid() const {
  // Reject inverted deadbands: a hysteresis band that would chatter must never
  // be applied to a physical actuator.
  if (temp.off >= temp.on) {
    return false;
  }
  if (humidity.on >= humidity.off) {
    return false;
  }
  if (soil.on >= soil.off) {
    return false;
  }
  return true;
}

String RuntimeConfig::toJson() const {
  StaticJsonDocument<1024> doc;
  doc["version"] = version;
  doc["crop"] = crop;

  JsonObject hysteresis = doc.createNestedObject("hysteresis");
  JsonObject tempObj = hysteresis.createNestedObject("temp");
  tempObj["on_above"] = temp.on;
  tempObj["off_below"] = temp.off;
  JsonObject humidityObj = hysteresis.createNestedObject("humidity");
  humidityObj["on_below"] = humidity.on;
  humidityObj["off_above"] = humidity.off;
  JsonObject soilObj = hysteresis.createNestedObject("soil");
  soilObj["on_below_pct"] = soil.on;
  soilObj["off_above_pct"] = soil.off;

  JsonObject irrigation = doc.createNestedObject("irrigation");
  irrigation["enabled"] = irrigation_enabled;

  JsonObject safety = doc.createNestedObject("safety");
  JsonObject maxOn = safety.createNestedObject("max_on_seconds");
  maxOn["fan"] = max_on_fan_s;
  maxOn["humidifier"] = max_on_humidifier_s;
  maxOn["pump"] = max_on_pump_s;

  String out;
  serializeJson(doc, out);
  return out;
}
