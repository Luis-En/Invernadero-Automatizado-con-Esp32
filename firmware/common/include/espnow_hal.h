#pragma once

#include <Arduino.h>

// Cross-platform ESP-NOW driver. It hides the API differences between the
// ESP32 core (2.x and 3.x callbacks) and the ESP8266 core (role management,
// different callback signatures, bool return values).
//
// Received frames go into a small ring buffer and are read from the main
// loop, never handled in the Wi-Fi callback. A ring buffer is used instead of
// a FreeRTOS queue because the ESP8266 non-OS SDK does not provide one.

static const uint8_t ESPNOW_MAX_PAYLOAD = 250;
static const uint8_t ESPNOW_QUEUE_LENGTH = 8;

struct EspNowMessage {
  uint8_t mac[6];
  int8_t rssi;
  uint8_t length;
  uint8_t data[ESPNOW_MAX_PAYLOAD];
};

class EspNowHal {
 public:
  // WIFI_MODE_STA by default. A node that already runs a soft AP (the field
  // node hosting the camera) must pass WIFI_MODE_APSTA so begin() does not
  // tear the AP down.
  enum WifiModeHint : uint8_t {
    MODE_KEEP_STA = 0,
    MODE_KEEP_APSTA = 1,
  };

  bool begin(uint8_t channel = 1, uint8_t mode_hint = MODE_KEEP_STA);
  bool send(const uint8_t* mac, const uint8_t* data, size_t length);
  bool sendBroadcast(const uint8_t* data, size_t length);
  bool poll(EspNowMessage& out, uint32_t timeoutMs = 0);

  const uint8_t* ownMac() const { return own_mac_; }
  uint16_t nextSeq() { return ++seq_; }
  bool lastSendOk() const { return last_send_ok_; }
  uint32_t dropped() const { return dropped_; }

  // Public so the per-platform callback trampolines can reach them.
  static void handleReceive(const uint8_t* mac, int8_t rssi, const uint8_t* data, uint8_t length);
  static void handleSend(bool ok);

 private:
  bool addPeer(const uint8_t* mac);
  bool push(const EspNowMessage& message);
  bool pop(EspNowMessage& out);

  static EspNowHal* instance_;
  uint8_t channel_ = 1;
  uint8_t own_mac_[6] = {0};
  uint16_t seq_ = 0;
  volatile bool last_send_ok_ = true;
  volatile uint32_t dropped_ = 0;

  EspNowMessage buffer_[ESPNOW_QUEUE_LENGTH];
  volatile uint8_t head_ = 0;
  volatile uint8_t tail_ = 0;
  volatile uint8_t count_ = 0;
};

extern EspNowHal espNow;
