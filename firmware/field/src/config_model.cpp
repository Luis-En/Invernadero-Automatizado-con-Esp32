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

// Seconds are bounded so a negative value can never wrap to ~49 days and a
// zero means "use the default", never "unlimited".
static bool readSeconds(JsonVariantConst value, uint32_t fallback, uint32_t& out) {
  if (value.isNull()) {
    out = fallback;
    return true;
  }
  if (!(value.is<int>() || value.is<long>() || value.is<unsigned long>() ||
        value.is<long long>() || value.is<unsigned long long>())) {
    return false;
  }
  long long raw = value.as<long long>();
  if (raw < 0 || raw > 86400LL) {
    return false;
  }
  out = (raw == 0) ? fallback : (uint32_t)raw;
  return true;
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
    if (!readSeconds(safety["fan"], next.max_on_fan_s, next.max_on_fan_s) ||
        !readSeconds(safety["humidifier"], next.max_on_humidifier_s, next.max_on_humidifier_s) ||
        !readSeconds(safety["pump"], next.max_on_pump_s, next.max_on_pump_s)) {
      return false;
    }
  }

  JsonVariantConst minOff = root["safety"]["min_off_seconds"];
  if (!minOff.isNull()) {
    if (!readSeconds(minOff["fan"], next.min_off_fan_s, next.min_off_fan_s) ||
        !readSeconds(minOff["humidifier"], next.min_off_humidifier_s, next.min_off_humidifier_s) ||
        !readSeconds(minOff["pump"], next.min_off_pump_s, next.min_off_pump_s)) {
      return false;
    }
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

  // Physical bounds. A value outside these ranges is a configuration bug,
  // not a plausible setpoint.
  if (temp.on < -10.0f || temp.on > 60.0f || temp.off < -10.0f || temp.off > 60.0f) {
    return false;
  }
  if (humidity.on < 0.0f || humidity.on > 100.0f ||
      humidity.off < 0.0f || humidity.off > 100.0f) {
    return false;
  }
  if (soil.on < 0.0f || soil.on > 100.0f ||
      soil.off < 0.0f || soil.off > 100.0f) {
    return false;
  }
  if (max_on_fan_s > 86400UL || max_on_humidifier_s > 86400UL ||
      max_on_pump_s > 86400UL) {
    return false;
  }
  if (min_off_fan_s > 86400UL || min_off_humidifier_s > 86400UL ||
      min_off_pump_s > 86400UL) {
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
  JsonObject minOff = safety.createNestedObject("min_off_seconds");
  minOff["fan"] = min_off_fan_s;
  minOff["humidifier"] = min_off_humidifier_s;
  minOff["pump"] = min_off_pump_s;

  String out;
  serializeJson(doc, out);
  return out;
}
