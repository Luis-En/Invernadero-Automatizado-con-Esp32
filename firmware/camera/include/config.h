#pragma once

// ESP32-CAM node configuration. The camera joins the field node's Wi-Fi access
// point and POSTs each JPEG to it. The field node then forwards the picture to
// the gateway over ESP-NOW, so no router is needed in the greenhouse.

#define CAM_FW_VERSION "2.0.0"
#define CAM_DEVICE_ID "camera"

// Capture cadence. The default is every 30 minutes.
#define CAM_CAPTURE_INTERVAL_MS (30UL * 60UL * 1000UL)
// First capture after boot: keep it short so the pipeline can be verified.
#define CAM_FIRST_CAPTURE_DELAY_MS 20000UL

// VGA at quality 12 is a good size/quality trade-off for ESP-NOW forwarding.
#define CAM_FRAME_SIZE FRAMESIZE_VGA
#define CAM_JPEG_QUALITY 12

// Wi-Fi credentials of the field node's access point. Must match
// firmware/field/include/config.h (FIELD_AP_*).
#define CAM_WIFI_SSID "invernadero-campo"
#define CAM_WIFI_PASSWORD "invernadero123"
#define CAM_WIFI_CHANNEL 6

// Where to POST the JPEG on the field node.
#define CAM_FIELD_HOST "192.168.4.1"
#define CAM_FIELD_PORT 80
#define CAM_PHOTO_PATH "/photo"
#define CAM_HEALTH_PATH "/health"

#define CAM_WIFI_CONNECT_TIMEOUT_MS 15000UL
#define CAM_UPLOAD_TIMEOUT_MS 20000UL
