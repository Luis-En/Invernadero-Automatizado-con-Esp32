#pragma once

#define GW_FW_VERSION_MAJOR 1
#define GW_FW_VERSION_MINOR 0
#define GW_FW_VERSION_PATCH 0
#define GW_FW_VERSION "1.0.0"

#define GW_DEVICE_ID "gateway_esp32"

#define GW_SERIAL_BAUD 115200

// The inbound line buffer plus the JSON document live in RAM for the whole
// run, so the ESP8266 (80 KB total) gets a smaller one. 2 KB fits the config
// JSON the Pi sends.
#if defined(ESP8266)
#define GW_MAX_SERIAL_LINE 2048
#else
#define GW_MAX_SERIAL_LINE 4096
#endif

#define GW_HEARTBEAT_INTERVAL_MS 30000UL
#define GW_DEVICE_TIMEOUT_MS 300000UL
// Must match the field node's AP/ESP-NOW channel (firmware/field config.h,
// FIELD_ESPNOW_CHANNEL).
#define GW_WIFI_CHANNEL 6

#define GW_ESPNOW_QUEUE_LENGTH 16

#ifndef GW_SIMULATE
#define GW_SIMULATE 0
#endif

// Bring-up diagnostic: print the source MAC and RSSI of every telemetry frame
// as a "# [gw] ..." comment line on the serial port. The bridge ignores lines
// starting with '#'. Set to 0 for normal operation.
#ifndef GW_DEBUG_PEERS
#define GW_DEBUG_PEERS 0
#endif

#define GW_SIM_TELEMETRY_INTERVAL_SEC 30
#define GW_SIM_PHOTO_INTERVAL_SEC (30 * 60)
