#include "espnow_hal.h"

#if defined(ESP8266)
#include <ESP8266WiFi.h>
#include <espnow.h>
#else
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <freertos/FreeRTOS.h>
#include <freertos/portmacro.h>
#endif

namespace {
const uint8_t kBroadcastMac[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
}

// The receive callback runs on the Wi-Fi task (ESP32: core 0, ESP8266: the SDK
// task), so the ring buffer needs a lock that is valid across those contexts.
#if defined(ESP8266)
#define ESPNOW_LOCK() noInterrupts()
#define ESPNOW_UNLOCK() interrupts()
#else
portMUX_TYPE g_espNowMux = portMUX_INITIALIZER_UNLOCKED;
#define ESPNOW_LOCK() portENTER_CRITICAL(&g_espNowMux)
#define ESPNOW_UNLOCK() portEXIT_CRITICAL(&g_espNowMux)
#endif

EspNowHal espNow;
EspNowHal* EspNowHal::instance_ = nullptr;

#if defined(ESP8266)
static void espNowRecvTrampoline(uint8_t* mac, uint8_t* data, uint8_t length) {
  EspNowHal::handleReceive(mac, 0, data, length);
}
static void espNowSendTrampoline(uint8_t* mac, uint8_t status) {
  EspNowHal::handleSend(status == 0);
}
#elif ESP_ARDUINO_VERSION_MAJOR >= 3
static void espNowRecvTrampoline(const esp_now_recv_info_t* info, const uint8_t* data, int length) {
  const uint8_t* mac = (info != nullptr) ? info->src_addr : nullptr;
  int8_t rssi = (info != nullptr && info->rx_ctrl != nullptr) ? (int8_t)info->rx_ctrl->rssi : 0;
  EspNowHal::handleReceive(mac, rssi, data, (uint8_t)length);
}
static void espNowSendTrampoline(const uint8_t* mac, esp_now_send_status_t status) {
  EspNowHal::handleSend(status == ESP_NOW_SEND_SUCCESS);
}
#else
static void espNowRecvTrampoline(const uint8_t* mac, const uint8_t* data, int length) {
  EspNowHal::handleReceive(mac, 0, data, (uint8_t)length);
}
static void espNowSendTrampoline(const uint8_t* mac, esp_now_send_status_t status) {
  EspNowHal::handleSend(status == ESP_NOW_SEND_SUCCESS);
}
#endif

bool EspNowHal::begin(uint8_t channel, uint8_t mode_hint) {
  instance_ = this;
  channel_ = channel;

#if defined(ESP8266)
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  WiFi.macAddress(own_mac_);
  wifi_set_channel(channel);
  if (esp_now_init() != 0) {
    return false;
  }
  esp_now_set_self_role(ESP_NOW_ROLE_COMBO);
  esp_now_register_recv_cb(espNowRecvTrampoline);
  esp_now_register_send_cb(espNowSendTrampoline);
  if (esp_now_add_peer((uint8_t*)kBroadcastMac, ESP_NOW_ROLE_COMBO, channel, nullptr, 0) != 0) {
    return false;
  }
#else
  // Do not force STA when the node already raised a soft AP: switching mode
  // would drop the AP and the camera would lose its network.
  if (mode_hint == MODE_KEEP_APSTA) {
    WiFi.mode(WIFI_AP_STA);
  } else if (WiFi.getMode() != WIFI_AP && WiFi.getMode() != WIFI_AP_STA) {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
  }
  delay(50);
  WiFi.macAddress(own_mac_);
  esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE);
  if (esp_now_init() != ESP_OK) {
    return false;
  }
  esp_now_register_recv_cb(espNowRecvTrampoline);
  esp_now_register_send_cb(espNowSendTrampoline);
  if (!addPeer(kBroadcastMac)) {
    return false;
  }
#endif

  return true;
}

bool EspNowHal::addPeer(const uint8_t* mac) {
#if defined(ESP8266)
  if (esp_now_is_peer_exist((uint8_t*)mac)) {
    return true;
  }
  return esp_now_add_peer((uint8_t*)mac, ESP_NOW_ROLE_COMBO, channel_, nullptr, 0) == 0;
#else
  if (esp_now_is_peer_exist(mac)) {
    return true;
  }
  esp_now_peer_info_t peer;
  memset(&peer, 0, sizeof(peer));
  memcpy(peer.peer_addr, mac, 6);
  peer.channel = 0;
  peer.encrypt = false;
  peer.ifidx = WIFI_IF_STA;
  return esp_now_add_peer(&peer) == ESP_OK;
#endif
}

bool EspNowHal::send(const uint8_t* mac, const uint8_t* data, size_t length) {
  if (length == 0 || length > ESPNOW_MAX_PAYLOAD) {
    return false;
  }
#if defined(ESP8266)
  if (!addPeer(mac)) {
    return false;
  }
  return esp_now_send((uint8_t*)mac, (uint8_t*)data, (uint8_t)length) == 0;
#else
  if (!addPeer(mac)) {
    return false;
  }
  return esp_now_send(mac, data, length) == ESP_OK;
#endif
}

bool EspNowHal::sendBroadcast(const uint8_t* data, size_t length) {
  return send(kBroadcastMac, data, length);
}

bool EspNowHal::poll(EspNowMessage& out, uint32_t timeoutMs) {
  uint32_t start = millis();
  while (true) {
    if (pop(out)) {
      return true;
    }
    if (timeoutMs == 0 || (millis() - start) >= timeoutMs) {
      return false;
    }
    delay(1);
  }
}

bool EspNowHal::push(const EspNowMessage& message) {
  bool stored = false;
  ESPNOW_LOCK();
  if (count_ < ESPNOW_QUEUE_LENGTH) {
    buffer_[head_] = message;
    head_ = (uint8_t)((head_ + 1) % ESPNOW_QUEUE_LENGTH);
    count_++;
    stored = true;
  } else {
    dropped_++;
  }
  ESPNOW_UNLOCK();
  return stored;
}

bool EspNowHal::pop(EspNowMessage& out) {
  bool available = false;
  ESPNOW_LOCK();
  if (count_ > 0) {
    out = buffer_[tail_];
    tail_ = (uint8_t)((tail_ + 1) % ESPNOW_QUEUE_LENGTH);
    count_--;
    available = true;
  }
  ESPNOW_UNLOCK();
  return available;
}

void EspNowHal::handleReceive(const uint8_t* mac, int8_t rssi, const uint8_t* data, uint8_t length) {
  if (instance_ == nullptr || mac == nullptr) {
    return;
  }
  if (length == 0 || length > ESPNOW_MAX_PAYLOAD) {
    return;
  }

  EspNowMessage message;
  memcpy(message.mac, mac, 6);
  message.rssi = rssi;
  message.length = length;
  memcpy(message.data, data, length);
  instance_->push(message);
}

void EspNowHal::handleSend(bool ok) {
  if (instance_ != nullptr) {
    instance_->last_send_ok_ = ok;
  }
}
