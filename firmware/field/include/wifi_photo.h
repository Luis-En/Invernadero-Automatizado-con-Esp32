#pragma once

#include <Arduino.h>
#include <WebServer.h>

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
// WebServer's regular `arg("plain")` path builds a `String` from a `char*`, so a
// binary JPEG is truncated at its first zero byte (4 bytes in). To receive the
// raw body intact this module registers its own RequestHandler and consumes the
// `HTTPRaw` chunks directly.
//
// Forwarding is spread over FIELD_PHOTO_SEND_WINDOW_MS instead of bursting all
// fragments back to back: a burst of ~80 ESP-NOW frames overruns the receiver
// and loses most of them. Two buffers are kept so a new upload can be accepted
// while the previous photo is still being sent out.

class WifiPhotoReceiver {
 public:
  // Starts the soft AP and the HTTP server.
  void begin();

  // Serve pending HTTP requests and advance the paced forwarding. Call often
  // from loop().
  void poll();

  bool apActive() const { return ap_active_; }
  uint8_t clientCount() const { return client_count_; }

  uint32_t framesReceived() const { return frames_received_; }
  uint32_t framesRejected() const { return frames_rejected_; }
  uint32_t chunksForwarded() const { return chunks_forwarded_; }

  // Called by the raw HTTP handler for each chunk of the POST body.
  void handleRaw(const HTTPRaw& raw);

 private:
  static uint16_t nextSequence();

  // Index of a buffer that is neither being sent nor waiting to be sent, or -1
  // when both are busy.
  int8_t freeBufferIndex() const;

  // Begin forwarding the complete photo held in buffers_[index].
  void startSending(int8_t index);

  // Emit the next fragment of the active photo.
  void sendNextChunk();

  // Send one fragment when its scheduled time has arrived.
  void tickForwarding(uint32_t now_ms);

  bool ap_active_ = false;
  uint8_t client_count_ = 0;
  uint32_t frames_received_ = 0;
  uint32_t frames_rejected_ = 0;
  uint32_t chunks_forwarded_ = 0;

  static const size_t kBufferMax = FIELD_PHOTO_BUFFER_MAX;
  uint8_t* buffers_[2] = {nullptr, nullptr};
  size_t buffer_length_[2] = {0, 0};
  uint16_t buffer_sequence_[2] = {0, 0};

  int8_t rx_index_ = -1;       // buffer currently receiving, -1 when idle
  int8_t send_index_ = -1;     // buffer being forwarded, -1 when idle
  int8_t pending_index_ = -1;  // complete buffer waiting its turn

  // Raw-body accumulation state.
  size_t raw_length_ = 0;
  bool raw_overflow_ = false;
  uint16_t raw_sequence_ = 0;

  // Active forward state.
  size_t tx_length_ = 0;
  uint16_t tx_sequence_ = 0;
  uint16_t tx_total_ = 0;
  uint16_t tx_next_chunk_ = 0;
  uint32_t tx_next_ms_ = 0;
  uint32_t tx_interval_ms_ = 1;
};

extern WifiPhotoReceiver wifiPhoto;
