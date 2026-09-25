#pragma once

#include <Arduino.h>
#include "esp_camera.h"

#include "config.h"

// Captures JPEGs with the OV2640 and hands them to the UART sender.
class CameraCapture {
 public:
  bool begin();
  bool ready() const { return ready_; }

  // Capture one frame. Returns a pointer to the internal framebuffer; the
  // caller must call release() when done. Returns nullptr on failure.
  camera_fb_t* capture();
  void release(camera_fb_t* frame);

  const char* lastError() const { return last_error_; }

 private:
  bool ready_ = false;
  const char* last_error_ = "";
};
