#pragma once

#include <Arduino.h>

// Non-volatile state plus the wall clock the gateway stamps forwarded
// telemetry with. The field node may boot without a synced clock, so the
// gateway keeps its own epoch (set by a timesync command from the Pi) and
// persists the last known value across reboots.
//
// ESP32 uses the Preferences library; the ESP8266 non-OS SDK has no
// Preferences, so it falls back to the EEPROM emulation.
class StateStore {
 public:
  void begin();

  uint16_t configVersion() const { return configVersion_; }
  void setConfigVersion(uint16_t version);

  void syncEpoch(uint32_t epoch);
  bool timeSynced() const { return timeSynced_; }
  uint32_t now() const;
  void formatIso(uint32_t epoch, char* out, size_t outLen) const;

 private:
  uint16_t configVersion_ = 0;
  bool timeSynced_ = false;
  uint32_t epochBase_ = 0;
  uint32_t epochBaseMillis_ = 0;
};

extern StateStore state;
