#include "wifi_photo.h"

#include <WiFi.h>
#include <WebServer.h>

#include "espnow_hal.h"
#include "field_link.h"

WifiPhotoReceiver wifiPhoto;

namespace {
WebServer server(FIELD_PHOTO_TCP_PORT);
uint16_t photo_sequence = 0;

// Registers a handler that consumes the raw POST body (binary-safe) for the
// camera's JPEG uploads. The stock `server.on()` handler loses the binary body
// to a null-terminated String, so the photo must be read through HTTPRaw.
class PhotoRawHandler : public RequestHandler {
 public:
  bool canHandle(HTTPMethod method, String uri) override {
    return method == HTTP_POST && uri == "/photo";
  }

  bool canRaw(String uri) override {
    (void)uri;
    return true;
  }

  void raw(WebServer& server, String uri, HTTPRaw& raw) override {
    (void)server;
    (void)uri;
    wifiPhoto.handleRaw(raw);
  }

  bool handle(WebServer& server, HTTPMethod method, String uri) override {
    (void)method;
    (void)uri;
    if (wifiPhoto.lastUploadAccepted()) {
      server.send(200, "application/json", "{\"status\":\"ok\"}");
    } else {
      server.send(503, "application/json",
                  "{\"status\":\"rejected\",\"reason\":\"photo buffer unavailable\"}");
    }
    return true;
  }
};

PhotoRawHandler photo_raw_handler;
}  // namespace

uint16_t WifiPhotoReceiver::nextSequence() { return ++photo_sequence; }

void WifiPhotoReceiver::begin() {
  for (uint8_t i = 0; i < 2; i++) {
    buffers_[i] = (uint8_t*)malloc(kBufferMax);
    if (buffers_[i] == nullptr) {
      Serial.printf("[photo] buffer %u allocation FAILED\n", i);
    }
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
    Serial.printf("[photo] forwarding window %lu ms\n",
                  (unsigned long)FIELD_PHOTO_SEND_WINDOW_MS);
    fieldLink.sendEvent(0, "CAM_AP_UP", FIELD_AP_SSID);
  } else {
    fieldLink.sendEvent(2, "CAM_AP_FAIL", "softAP did not start");
  }

  server.addHandler(&photo_raw_handler);

  server.on("/health", HTTP_GET, []() {
    server.send(200, "application/json", "{\"status\":\"ok\",\"device\":\"field_esp32\"}");
  });

  server.onNotFound([]() {
    server.send(404, "text/plain", "not found");
  });

  server.begin();
  Serial.printf("[photo] HTTP server on port %d\n", FIELD_PHOTO_TCP_PORT);
}

int8_t WifiPhotoReceiver::freeBufferIndex() const {
  for (int8_t i = 0; i < 2; i++) {
    if (i != send_index_ && i != pending_index_) {
      return i;
    }
  }
  return -1;
}

void WifiPhotoReceiver::handleRaw(const HTTPRaw& raw) {
  switch (raw.status) {
    case RAW_START:
      raw_length_ = 0;
      raw_overflow_ = false;
      last_upload_accepted_ = false;
      raw_sequence_ = nextSequence();
      rx_index_ = freeBufferIndex();
      if (rx_index_ < 0 || buffers_[rx_index_] == nullptr) {
        raw_overflow_ = true;
        rx_index_ = -1;
        Serial.println("[photo] no free buffer, upload rejected");
      }
      break;

    case RAW_WRITE:
      if (rx_index_ < 0 || raw_overflow_ || buffers_[rx_index_] == nullptr ||
          raw.buf == nullptr) {
        raw_overflow_ = true;
        break;
      }
      if (raw_length_ + raw.currentSize > kBufferMax) {
        raw_overflow_ = true;
        break;
      }
      memcpy(buffers_[rx_index_] + raw_length_, raw.buf, raw.currentSize);
      raw_length_ += raw.currentSize;
      break;

    case RAW_END:
      if (rx_index_ >= 0 && buffers_[rx_index_] != nullptr &&
          !raw_overflow_ && raw_length_ > 0) {
        buffer_length_[rx_index_] = raw_length_;
        buffer_sequence_[rx_index_] = raw_sequence_;
        frames_received_++;
        last_upload_accepted_ = true;

        Serial.printf("[photo] frame %u received over WiFi: %u bytes\n",
                      (unsigned)raw_sequence_, (unsigned)raw_length_);

        char detail[64];
        snprintf(detail, sizeof(detail), "seq=%u bytes=%u",
                 (unsigned)raw_sequence_, (unsigned)raw_length_);
        fieldLink.sendEvent(0, "PHOTO_OK", detail);

        // Hand the buffer to the paced sender. If a photo is already going out,
        // park this one; the sender picks it up when it finishes.
        if (send_index_ < 0) {
          startSending(rx_index_);
        } else if (pending_index_ < 0) {
          pending_index_ = rx_index_;
          Serial.printf("[photo] frame %u queued behind the active send\n",
                        (unsigned)raw_sequence_);
        } else {
          frames_rejected_++;
          last_upload_accepted_ = false;
          Serial.println("[photo] send queue full, frame dropped");
        }
      } else {
        frames_rejected_++;
        if (raw_overflow_) {
          Serial.printf("[photo] frame %u rejected (overflow/busy)\n",
                        (unsigned)raw_sequence_);
        }
      }
      rx_index_ = -1;
      break;

    case RAW_ABORTED:
      frames_rejected_++;
      last_upload_accepted_ = false;
      rx_index_ = -1;
      Serial.println("[photo] upload aborted");
      break;
  }
}

void WifiPhotoReceiver::startSending(int8_t index) {
  if (index < 0 || buffers_[index] == nullptr) {
    return;
  }
  send_index_ = index;
  tx_length_ = buffer_length_[index];
  tx_sequence_ = buffer_sequence_[index];
  tx_total_ = (uint16_t)((tx_length_ + ESPNOW_PHOTO_DATA_MAX - 1) / ESPNOW_PHOTO_DATA_MAX);
  tx_next_chunk_ = 0;
  tx_next_ms_ = millis();

  // Spread the whole frame over the configured window. With ~80 fragments and a
  // 120 s window that is one frame every ~1.5 s, slow enough that the receiver
  // never overruns.
  if (tx_total_ == 0) {
    tx_interval_ms_ = 1;
  } else {
    uint32_t interval = FIELD_PHOTO_SEND_WINDOW_MS / tx_total_;
    tx_interval_ms_ = interval < 1 ? 1 : interval;
  }

  Serial.printf("[photo] frame %u sending as %u chunks every %lu ms\n",
                (unsigned)tx_sequence_, (unsigned)tx_total_,
                (unsigned long)tx_interval_ms_);
}

void WifiPhotoReceiver::sendNextChunk() {
  if (send_index_ < 0 || buffers_[send_index_] == nullptr ||
      tx_next_chunk_ >= tx_total_) {
    return;
  }

  const uint8_t* data = buffers_[send_index_];
  const uint16_t index = tx_next_chunk_;
  size_t offset = (size_t)index * ESPNOW_PHOTO_DATA_MAX;
  size_t remaining = tx_length_ - offset;
  uint16_t chunk_len =
      (uint16_t)(remaining > ESPNOW_PHOTO_DATA_MAX ? ESPNOW_PHOTO_DATA_MAX : remaining);

  PhotoChunkMsg msg;
  memset(&msg, 0, sizeof(msg));
  msg.hdr.magic = ESPNOW_MAGIC;
  msg.hdr.version = ESPNOW_PROTO_VERSION;
  msg.hdr.type = MSG_PHOTO_CHUNK;
  memcpy(msg.hdr.src, espNow.ownMac(), 6);
  msg.hdr.seq = espNow.nextSeq();
  msg.sequence = tx_sequence_;
  msg.total_chunks = tx_total_;
  msg.chunk_index = index;
  msg.crc16 = crc16_ccitt(data + offset, chunk_len);
  msg.data_len = chunk_len;
  memcpy(msg.data, data + offset, chunk_len);

  fieldLink.sendToGateway((const uint8_t*)&msg, sizeof(msg));
  chunks_forwarded_++;
  tx_next_chunk_++;

  if (tx_next_chunk_ >= tx_total_) {
    Serial.printf("[photo] frame %u forwarded as %u chunks\n",
                  (unsigned)tx_sequence_, (unsigned)tx_total_);
    send_index_ = -1;
    if (pending_index_ >= 0) {
      int8_t next = pending_index_;
      pending_index_ = -1;
      startSending(next);
    }
  }
}

void WifiPhotoReceiver::tickForwarding(uint32_t now_ms) {
  if (send_index_ < 0) {
    return;
  }
  if ((int32_t)(now_ms - tx_next_ms_) < 0) {
    return;
  }
  sendNextChunk();
  tx_next_ms_ = now_ms + tx_interval_ms_;
}

void WifiPhotoReceiver::poll() {
  server.handleClient();
  client_count_ = WiFi.softAPgetStationNum();
  tickForwarding(millis());
}
