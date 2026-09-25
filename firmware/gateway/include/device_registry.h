#pragma once

#include <Arduino.h>

#include "protocol.h"

struct DeviceRecord {
  bool used;
  uint8_t mac[6];
  uint8_t role;
  char device_id[16];
  int8_t rssi;
  uint32_t last_seen_ms;
  uint32_t last_seen_epoch;
};

// Tracks the peers the gateway has heard from, keyed by MAC. Used to route
// commands to the right node and to raise the 5 minute offline watchdog.
class DeviceRegistry {
 public:
  void begin();
  void update(const uint8_t* mac, uint8_t role, const char* deviceId, int8_t rssi, uint32_t epoch);

  const DeviceRecord* findRole(uint8_t role) const;
  bool macForRole(uint8_t role, uint8_t* outMac) const;
  bool isOnline(uint8_t role, uint32_t nowMs, uint32_t timeoutMs) const;
  int8_t rssiForRole(uint8_t role) const;
  uint32_t secondsSinceSeen(uint8_t role, uint32_t nowMs) const;
  const char* deviceIdForRole(uint8_t role) const;

 private:
  static const size_t kMaxDevices = 8;
  DeviceRecord* findOrCreate(const uint8_t* mac);
  DeviceRecord devices_[kMaxDevices];
};

extern DeviceRegistry registry;
