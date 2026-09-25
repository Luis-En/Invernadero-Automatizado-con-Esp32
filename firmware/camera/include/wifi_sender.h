#pragma once

#include <Arduino.h>

#include "config.h"

// Sends a captured JPEG to the field node over Wi-Fi. The camera joins the
// field node's access point and POSTs the whole image to /photo; the field node
// then fragments and forwards it over ESP-NOW.
//
// The connection is kept alive between uploads so each capture only pays the
// HTTP request cost, not a fresh TCP handshake.
class WifiPhotoSender {
 public:
  void begin();

  // Try to (re)connect to the field access point. Returns true when connected.
  bool ensureConnected();

  // POST a JPEG to the field node. Reconnects once if the socket was dropped.
  bool send(const uint8_t* data, size_t length, uint16_t sequence);

  bool connected() const { return connected_; }
  int8_t lastRssi() const { return last_rssi_; }
  uint16_t nextSequence() { return ++sequence_; }

 private:
  bool postOnce(const uint8_t* data, size_t length, uint16_t sequence);

  uint16_t sequence_ = 0;
  bool connected_ = false;
  int8_t last_rssi_ = 0;
  uint32_t last_connect_attempt_ms_ = 0;
};

extern WifiPhotoSender photoSender;
