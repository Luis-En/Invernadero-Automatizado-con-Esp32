#include "persistence.h"

#include <Preferences.h>

Persistence persistence;

namespace {
Preferences prefs;
const char* kNamespace = "greenhouse";

// Calibration keys: "cd0".."cd5" for dry ADC, "cw0".."cw5" for wet ADC.
void calDryKey(uint8_t index, char* out, size_t size) {
  snprintf(out, size, "cd%u", (unsigned)index);
}
void calWetKey(uint8_t index, char* out, size_t size) {
  snprintf(out, size, "cw%u", (unsigned)index);
}
}  // namespace

void Persistence::begin() {
  ready_ = prefs.begin(kNamespace, false);
}

bool Persistence::saveConfig(const RuntimeConfig& config) {
  if (!ready_) {
    return false;
  }
  String json = config.toJson();
  size_t written = prefs.putString("config", json);
  prefs.putUShort("config_ver", config.version);
  prefs.putUShort("config_crc", configCrc16(json.c_str(), json.length()));
  return written == json.length();
}

bool Persistence::loadConfig(RuntimeConfig& out) {
  if (!ready_) {
    return false;
  }
  String json = prefs.getString("config", "");
  if (json.length() == 0) {
    return false;
  }
  uint16_t stored_crc = prefs.getUShort("config_crc", 0);
  if (stored_crc != 0 && stored_crc != configCrc16(json.c_str(), json.length())) {
    // Corrupted record: refuse to apply it rather than drive actuators with
    // garbage thresholds.
    return false;
  }
  return out.fromJson(json);
}

bool Persistence::hasConfig() {
  if (!ready_) {
    return false;
  }
  return prefs.isKey("config");
}

bool Persistence::saveCalibration(const SensorManager::Calibration* calibration, size_t count) {
  if (!ready_) {
    return false;
  }
  for (size_t i = 0; i < count; i++) {
    char dry_key[8];
    char wet_key[8];
    calDryKey((uint8_t)i, dry_key, sizeof(dry_key));
    calWetKey((uint8_t)i, wet_key, sizeof(wet_key));
    prefs.putUShort(dry_key, calibration[i].dry_adc);
    prefs.putUShort(wet_key, calibration[i].wet_adc);
  }
  return true;
}

bool Persistence::loadCalibration(SensorManager::Calibration* out, size_t count) {
  if (!ready_) {
    return false;
  }
  bool loaded = false;
  for (size_t i = 0; i < count; i++) {
    char dry_key[8];
    char wet_key[8];
    calDryKey((uint8_t)i, dry_key, sizeof(dry_key));
    calWetKey((uint8_t)i, wet_key, sizeof(wet_key));
    if (prefs.isKey(dry_key)) {
      out[i].dry_adc = prefs.getUShort(dry_key, out[i].dry_adc);
      out[i].wet_adc = prefs.getUShort(wet_key, out[i].wet_adc);
      loaded = true;
    }
  }
  return loaded;
}

void Persistence::clear() {
  if (ready_) {
    prefs.clear();
  }
}
