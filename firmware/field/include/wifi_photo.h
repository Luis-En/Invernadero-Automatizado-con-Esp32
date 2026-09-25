#pragma once

#include <Arduino.h>

#include "config.h"
#include "protocol.h"

// Receives JPEG captures from the ESP32-CAM over Wi-Fi and forwards them to the
// gateway as ESP-NOW photo chunks.
//
// The camera and the field node are up to 50 m apart with no router, so the
// field node runs a soft access point (AP) and the camera joins it. The camera
// POSTs the whole JPEG to /photo in one request; this module buffers it and
// emits ESPNOW_PHOTO_DATA_MAX-byte fragments, the same path the old UART link
// used, only over Wi-Fi.
//
// The JPEG is buffered in heap. A VGA frame is ~30 KB and the ESP32 has enough
// free heap once the camera is not in use, so a single frame is held at a time
// and rejected if it does not fit.

class WifiPhotoReceiver {
 public:
  // Starts the soft AP and the HTTP server.
  void begin();

  // Serve pending HTTP requests. Call often from loop().
  void poll();

  bool apActive() const { return ap_active_; }
  uint8_t clientCount() const { return client_count_; }

  uint32_t framesReceived() const { return frames_received_; }
  uint32_t framesRejected() const { return frames_rejected_; }
  uint32_t chunksForwarded() const { return chunks_forwarded_; }

 private:
  void handlePhoto();
  void forwardBuffer(const uint8_t* data, size_t length, uint16_t sequence);
  static uint16_t nextSequence();

  bool ap_active_ = false;
  uint8_t client_count_ = 0;
  uint32_t frames_received_ = 0;
  uint32_t frames_rejected_ = 0;
  uint32_t chunks_forwarded_ = 0;

  uint8_t* buffer_ = nullptr;
  static const size_t kBufferMax = FIELD_PHOTO_BUFFER_MAX;
};

extern WifiPhotoReceiver wifiPhoto;
