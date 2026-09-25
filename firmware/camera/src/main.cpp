#include <Arduino.h>

#include "camera_capture.h"
#include "config.h"
#include "wifi_sender.h"

namespace {
constexpr uint32_t kFirstCaptureDelayMs = CAM_FIRST_CAPTURE_DELAY_MS;
constexpr uint32_t kCaptureIntervalMs = CAM_CAPTURE_INTERVAL_MS;
// While a frame has not been uploaded yet, retry often instead of waiting the
// full capture interval. Once one succeeds, the normal cadence takes over.
constexpr uint32_t kRetryIntervalMs = 15000UL;
constexpr uint32_t kHeartbeatIntervalMs = 20000UL;

CameraCapture camera;
uint32_t boot_ms = 0;
uint32_t last_capture_ms = 0;
uint32_t last_heartbeat_ms = 0;
bool first_capture_done = false;
bool have_uploaded_once = false;
uint32_t failed_attempts = 0;
uint16_t last_frame_bytes = 0;

void printBanner() {
  Serial.println();
  Serial.println("========================================");
  Serial.printf("[camera] firmware %s\n", CAM_FW_VERSION);
  Serial.printf("[camera] camera %s\n", camera.ready() ? "ready" : "NOT ready");
  if (!camera.ready()) {
    Serial.printf("[camera] error: %s\n", camera.lastError());
  }
  Serial.printf("[camera] Wi-Fi %s  ssid=%s\n",
                photoSender.connected() ? "connected" : "disconnected",
                CAM_WIFI_SSID);
  if (photoSender.connected()) {
    Serial.printf("[camera] POST -> http://%s:%d%s\n",
                  CAM_FIELD_HOST, CAM_FIELD_PORT, CAM_PHOTO_PATH);
    Serial.printf("[camera] rssi=%d\n", photoSender.lastRssi());
  }
  if (have_uploaded_once) {
    Serial.printf("[camera] last frame: %u bytes, failures=%lu\n",
                  (unsigned)last_frame_bytes, (unsigned long)failed_attempts);
  } else {
    Serial.printf("[camera] waiting for first capture (failed attempts=%lu)\n",
                  (unsigned long)failed_attempts);
  }
  Serial.println("========================================");
}

// Returns true when a frame was captured and uploaded.
bool captureAndSend() {
  camera_fb_t* frame = camera.capture();
  if (frame == nullptr) {
    Serial.println("[camera] capture FAILED (frame is null)");
    return false;
  }

  if (frame->format != PIXFORMAT_JPEG) {
    Serial.println("[camera] unexpected pixel format");
    camera.release(frame);
    return false;
  }

  uint16_t sequence = photoSender.nextSequence();
  last_frame_bytes = (uint16_t)frame->len;
  Serial.printf("[camera] frame %u: %u bytes, uploading\n", sequence,
                (unsigned)frame->len);

  bool ok = photoSender.send(frame->buf, frame->len, sequence);
  camera.release(frame);

  if (ok) {
    Serial.printf("[camera] frame %u uploaded\n", sequence);
    return true;
  }

  Serial.printf("[camera] frame %u UPLOAD FAILED\n", sequence);
  return false;
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);
  boot_ms = millis();
  last_capture_ms = millis();

  camera.begin();
  photoSender.begin();
  printBanner();
  last_heartbeat_ms = millis();
}

void loop() {
  const uint32_t now_ms = millis();

  // Decide when the next attempt is due.
  bool due = false;
  if (!have_uploaded_once) {
    // Still booting or retrying: attempt shortly after boot, then every retry
    // interval until one succeeds.
    if (!first_capture_done && (now_ms - boot_ms) >= kFirstCaptureDelayMs) {
      due = true;
    } else if (first_capture_done && (now_ms - last_capture_ms) >= kRetryIntervalMs) {
      due = true;
    }
  } else if ((now_ms - last_capture_ms) >= kCaptureIntervalMs) {
    due = true;
  }

  if (due && camera.ready()) {
    last_capture_ms = now_ms;
    first_capture_done = true;
    if (captureAndSend()) {
      have_uploaded_once = true;
    } else {
      failed_attempts++;
    }
  }

  if (now_ms - last_heartbeat_ms >= kHeartbeatIntervalMs) {
    last_heartbeat_ms = now_ms;
    printBanner();
  }

  delay(50);
}
