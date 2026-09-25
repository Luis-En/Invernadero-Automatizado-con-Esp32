#include "device_registry.h"

DeviceRegistry registry;

void DeviceRegistry::begin() {
  memset(devices_, 0, sizeof(devices_));
}

DeviceRecord* DeviceRegistry::findOrCreate(const uint8_t* mac) {
  for (size_t i = 0; i < kMaxDevices; i++) {
    if (devices_[i].used && memcmp(devices_[i].mac, mac, 6) == 0) {
      return &devices_[i];
    }
  }
  for (size_t i = 0; i < kMaxDevices; i++) {
    if (!devices_[i].used) {
      devices_[i].used = true;
      memcpy(devices_[i].mac, mac, 6);
      return &devices_[i];
    }
  }
  // Table full: evict the least recently seen entry.
  size_t oldest = 0;
  for (size_t i = 1; i < kMaxDevices; i++) {
    if (devices_[i].last_seen_ms < devices_[oldest].last_seen_ms) {
      oldest = i;
    }
  }
  memset(&devices_[oldest], 0, sizeof(devices_[oldest]));
  devices_[oldest].used = true;
  memcpy(devices_[oldest].mac, mac, 6);
  return &devices_[oldest];
}

void DeviceRegistry::update(const uint8_t* mac, uint8_t role, const char* deviceId, int8_t rssi,
                            uint32_t epoch) {
  DeviceRecord* record = findOrCreate(mac);
  record->role = role;
  record->rssi = rssi;
  record->last_seen_ms = millis();
  record->last_seen_epoch = epoch;
  if (deviceId != nullptr && deviceId[0] != '\0') {
    strncpy(record->device_id, deviceId, sizeof(record->device_id) - 1);
    record->device_id[sizeof(record->device_id) - 1] = '\0';
  }
}

const DeviceRecord* DeviceRegistry::findRole(uint8_t role) const {
  const DeviceRecord* best = nullptr;
  for (size_t i = 0; i < kMaxDevices; i++) {
    if (!devices_[i].used || devices_[i].role != role) {
      continue;
    }
    if (best == nullptr || devices_[i].last_seen_ms > best->last_seen_ms) {
      best = &devices_[i];
    }
  }
  return best;
}

bool DeviceRegistry::macForRole(uint8_t role, uint8_t* outMac) const {
  const DeviceRecord* record = findRole(role);
  if (record == nullptr) {
    return false;
  }
  memcpy(outMac, record->mac, 6);
  return true;
}

bool DeviceRegistry::isOnline(uint8_t role, uint32_t nowMs, uint32_t timeoutMs) const {
  const DeviceRecord* record = findRole(role);
  if (record == nullptr) {
    return false;
  }
  return (nowMs - record->last_seen_ms) <= timeoutMs;
}

int8_t DeviceRegistry::rssiForRole(uint8_t role) const {
  const DeviceRecord* record = findRole(role);
  return record != nullptr ? record->rssi : 0;
}

uint32_t DeviceRegistry::secondsSinceSeen(uint8_t role, uint32_t nowMs) const {
  const DeviceRecord* record = findRole(role);
  if (record == nullptr) {
    return UINT32_MAX;
  }
  return (nowMs - record->last_seen_ms) / 1000UL;
}

const char* DeviceRegistry::deviceIdForRole(uint8_t role) const {
  const DeviceRecord* record = findRole(role);
  return record != nullptr ? record->device_id : "";
}
