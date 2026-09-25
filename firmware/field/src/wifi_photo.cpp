#include "wifi_photo.h"

#include <WiFi.h>
#include <WebServer.h>

#include "espnow_hal.h"
#include "field_link.h"

WifiPhotoReceiver wifiPhoto;

namespace {
WebServer server(FIELD_PHOTO_TCP_PORT);
uint16_t photo_sequence = 0;

// Capacities for the HTTP layer. A VGA JPEG is ~30 KB and is uploaded as a
// single POST body, so the server must accept a body larger than its default
// 4 KB. WebServer stores it in the request's "plain" argument.
constexpr size_t kHttpBufferBytes = FIELD_PHOTO_BUFFER_MAX;
}  // namespace

uint16_t WifiPhotoReceiver::nextSequence() { return ++photo_sequence; }

void WifiPhotoReceiver::begin() {
  buffer_ = (uint8_t*)malloc(kBufferMax);
  if (buffer_ == nullptr) {
    Serial.println("[photo] buffer allocation FAILED");
  }

  WiFi.mode(WIFI_AP);
  IPAddress ap_ip(192, 168, 4, 1);
  IPAddress gateway(192, 168, 4, 1);
  IPAddress subnet(255, 255, 255, 0);
  WiFi.softAPConfig(ap_ip, gateway, subnet);
  ap_active_ = WiFi.softAP(FIELD_AP_SSID, FIELD_AP_PASSWORD, FIELD_AP_CHANNEL,
                           /*ssid_hidden=*/0, FIELD_AP_MAX_CLIENTS);

  Serial.printf("[photo] AP %s SSID=%s channel=%d IP=%s\n",
                ap_active_ ? "up" : "FAILED", FIELD_AP_SSID,
                FIELD_AP_CHANNEL, WiFi.softAPIP().toString().c_str());
  if (ap_active_) {
    Serial.printf("[photo] camera should POST to http://%s/photo\n",
                  WiFi.softAPIP().toString().c_str());
    fieldLink.sendEvent(0, "CAM_AP_UP", FIELD_AP_SSID);
  } else {
    fieldLink.sendEvent(2, "CAM_AP_FAIL", "softAP did not start");
  }

  server.on("/photo", HTTP_POST, [this]() { handlePhoto(); });

  server.on("/health", HTTP_GET, []() {
    server.send(200, "application/json", "{\"status\":\"ok\",\"device\":\"field_esp32\"}");
  });

  server.onNotFound([]() {
    server.send(404, "text/plain", "not found");
  });

  server.begin();
  Serial.printf("[photo] HTTP server on port %d\n", FIELD_PHOTO_TCP_PORT);
}

void WifiPhotoReceiver::handlePhoto() {
  if (buffer_ == nullptr) {
    server.send(500, "text/plain", "no buffer");
    frames_rejected_++;
    return;
  }

  // WebServer collects the raw request body into the "plain" argument when the
  // content type is not form-urlencoded. The camera sends image/jpeg.
  if (!server.hasArg("plain")) {
    Serial.println("[photo] POST without body");
    server.send(400, "text/plain", "empty body");
    frames_rejected_++;
    return;
  }

  const String& body = server.arg("plain");
  size_t length = body.length();
  if (length == 0) {
    server.send(400, "text/plain", "empty body");
    frames_rejected_++;
    return;
  }
  if (length > kBufferMax) {
    Serial.printf("[photo] frame too large: %u > %u\n",
                  (unsigned)length, (unsigned)kBufferMax);
    server.send(413, "text/plain", "too large");
    frames_rejected_++;
    return;
  }

  memcpy(buffer_, body.c_str(), length);

  uint16_t sequence = nextSequence();
  Serial.printf("[photo] frame %u received over WiFi: %u bytes\n",
                (unsigned)sequence, (unsigned)length);

  char detail[64];
  snprintf(detail, sizeof(detail), "seq=%u bytes=%u", (unsigned)sequence, (unsigned)length);
  fieldLink.sendEvent(0, "PHOTO_OK", detail);

  forwardBuffer(buffer_, length, sequence);
  server.send(200, "application/json", "{\"status\":\"ok\"}");
}

void WifiPhotoReceiver::forwardBuffer(const uint8_t* data, size_t length, uint16_t sequence) {
  const uint16_t total = (uint16_t)((length + ESPNOW_PHOTO_DATA_MAX - 1) / ESPNOW_PHOTO_DATA_MAX);

  for (uint16_t index = 0; index < total; index++) {
    size_t offset = (size_t)index * ESPNOW_PHOTO_DATA_MAX;
    size_t remaining = length - offset;
    uint16_t chunk_len = (uint16_t)(remaining > ESPNOW_PHOTO_DATA_MAX ? ESPNOW_PHOTO_DATA_MAX : remaining);

    PhotoChunkMsg msg;
    memset(&msg, 0, sizeof(msg));
    msg.hdr.magic = ESPNOW_MAGIC;
    msg.hdr.version = ESPNOW_PROTO_VERSION;
    msg.hdr.type = MSG_PHOTO_CHUNK;
    memcpy(msg.hdr.src, espNow.ownMac(), 6);
    msg.hdr.seq = espNow.nextSeq();
    msg.sequence = sequence;
    msg.total_chunks = total;
    msg.chunk_index = index;
    msg.crc16 = crc16_ccitt(data + offset, chunk_len);
    msg.data_len = chunk_len;
    memcpy(msg.data, data + offset, chunk_len);

    espNow.sendBroadcast((const uint8_t*)&msg, sizeof(msg));
    chunks_forwarded_++;

    // Pace the ESP-NOW burst so the radio and the control loop stay healthy.
    delay(3);
  }

  frames_received_++;
  Serial.printf("[photo] frame %u forwarded as %u chunks\n",
                (unsigned)sequence, (unsigned)total);
}

void WifiPhotoReceiver::poll() {
  server.handleClient();
  client_count_ = WiFi.softAPgetStationNum();
}
