#include "state_store.h"

#include <stdio.h>
#include <time.h>

#if defined(ESP8266)
#include <EEPROM.h>
#else
#include <Preferences.h>
#endif

namespace {
#if defined(ESP8266)
struct PersistedState {
  uint16_t magic;
  uint16_t config_version;
  uint32_t epoch;
};
const uint16_t kStoreMagic = 0x4752;  // 'GR'
const size_t kStoreSize = sizeof(PersistedState);

void loadPersisted(PersistedState& out) {
  EEPROM.begin(kStoreSize);
  EEPROM.get(0, out);
}

void savePersisted(const PersistedState& value) {
  EEPROM.put(0, value);
  EEPROM.commit();
}
#else
const char* kNvsNamespace = "greenhouse";
const char* kKeyConfigVersion = "cfg_ver";
const char* kKeyLastEpoch = "epoch";
Preferences prefs;
#endif
}  // namespace

StateStore state;

void StateStore::begin() {
#if defined(ESP8266)
  PersistedState stored;
  loadPersisted(stored);
  if (stored.magic != kStoreMagic) {
    return;
  }
  configVersion_ = stored.config_version;
  if (stored.epoch > 0) {
    epochBase_ = stored.epoch;
    epochBaseMillis_ = millis();
    timeSynced_ = true;
  }
#else
  prefs.begin(kNvsNamespace, false);
  configVersion_ = prefs.getUShort(kKeyConfigVersion, 0);

  uint32_t stored = prefs.getULong(kKeyLastEpoch, 0);
  if (stored > 0) {
    epochBase_ = stored;
    epochBaseMillis_ = millis();
    timeSynced_ = true;
  }
#endif
}

void StateStore::setConfigVersion(uint16_t version) {
  configVersion_ = version;
#if defined(ESP8266)
  PersistedState stored;
  loadPersisted(stored);
  if (stored.magic != kStoreMagic) {
    stored = {kStoreMagic, 0, 0};
  }
  stored.config_version = version;
  savePersisted(stored);
#else
  prefs.putUShort(kKeyConfigVersion, version);
#endif
}

void StateStore::syncEpoch(uint32_t epoch) {
  if (epoch == 0) {
    return;
  }
  epochBase_ = epoch;
  epochBaseMillis_ = millis();
  timeSynced_ = true;
#if defined(ESP8266)
  PersistedState stored;
  loadPersisted(stored);
  if (stored.magic != kStoreMagic) {
    stored = {kStoreMagic, 0, 0};
  }
  stored.epoch = epoch;
  savePersisted(stored);
#else
  prefs.putULong(kKeyLastEpoch, epoch);
#endif
}

uint32_t StateStore::now() const {
  if (!timeSynced_) {
    return 0;
  }
  return epochBase_ + (millis() - epochBaseMillis_) / 1000UL;
}

void StateStore::formatIso(uint32_t epoch, char* out, size_t outLen) const {
  if (epoch == 0) {
    snprintf(out, outLen, "1970-01-01T00:00:00Z");
    return;
  }
  time_t raw = (time_t)epoch;
  struct tm parts;
  gmtime_r(&raw, &parts);
  strftime(out, outLen, "%Y-%m-%dT%H:%M:%SZ", &parts);
}
