#include "wifi_sender.h"

#include <HTTPClient.h>
#include <WiFi.h>

WifiPhotoSender photoSender;

void WifiPhotoSender::begin() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // keep the link responsive for uploads
  Serial.printf("[camera] joining AP %s ...\n", CAM_WIFI_SSID);
  ensureConnected();
}

bool WifiPhotoSender::ensureConnected() {
  if (WiFi.status() == WL_CONNECTED) {
    connected_ = true;
    last_rssi_ = (int8_t)WiFi.RSSI();
    return true;
  }

  // Rate-limit reconnect attempts so the capture loop is not blocked spinning.
  uint32_t now = millis();
  if (now - last_connect_attempt_ms_ < 2000UL && last_connect_attempt_ms_ != 0) {
    return false;
  }
  last_connect_attempt_ms_ = now;

  connected_ = false;
  WiFi.disconnect();
  WiFi.begin(CAM_WIFI_SSID, CAM_WIFI_PASSWORD, CAM_WIFI_CHANNEL);

  uint32_t deadline = millis() + CAM_WIFI_CONNECT_TIMEOUT_MS;
  while (WiFi.status() != WL_CONNECTED && millis() < deadline) {
    delay(200);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    connected_ = true;
    last_rssi_ = (int8_t)WiFi.RSSI();
    Serial.printf("[camera] connected to %s, IP=%s rssi=%d\n",
                  CAM_WIFI_SSID, WiFi.localIP().toString().c_str(), last_rssi_);
    return true;
  }

  Serial.println("[camera] Wi-Fi connect FAILED");
  return false;
}

bool WifiPhotoSender::send(const uint8_t* data, size_t length, uint16_t sequence) {
  if (!ensureConnected()) {
    return false;
  }

  if (postOnce(data, length, sequence)) {
    return true;
  }

  // One retry after forcing a reconnect: the AP may have restarted.
  Serial.println("[camera] upload failed, reconnecting");
  connected_ = false;
  WiFi.disconnect();
  delay(500);
  if (!ensureConnected()) {
    return false;
  }
  return postOnce(data, length, sequence);
}

bool WifiPhotoSender::postOnce(const uint8_t* data, size_t length, uint16_t sequence) {
  String url = String("http://") + CAM_FIELD_HOST + ":" + CAM_FIELD_PORT + CAM_PHOTO_PATH;

  HTTPClient http;
  http.setConnectTimeout(CAM_UPLOAD_TIMEOUT_MS);
  http.setTimeout(CAM_UPLOAD_TIMEOUT_MS);
  http.setReuse(true);
  if (!http.begin(url)) {
    Serial.println("[camera] http.begin failed");
    return false;
  }

  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-Sequence", String(sequence));

  int status = http.POST((uint8_t*)data, length);
  http.end();

  if (status == 200) {
    return true;
  }
  Serial.printf("[camera] POST returned %d\n", status);
  return false;
}
