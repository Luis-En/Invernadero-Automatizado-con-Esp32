#pragma once

// ESP8266 gateway bring-up node. Receives ESP-NOW frames from the field node
// and forwards them to the PC over USB serial as JSON lines.

#define GW_FW_VERSION "0.1.0-bringup"
#define GW_DEVICE_ID "gateway_esp8266"

// Field node identity used as a fallback until a Hello frame is seen.
#define FIELD_DEVICE_ID_DEFAULT "field_esp8266"

#define SERIAL_BAUD 115200
#define ESPNOW_CHANNEL_DEFAULT 1

// How long a line buffer may grow before it is treated as garbage.
#define SERIAL_LINE_MAX 512
