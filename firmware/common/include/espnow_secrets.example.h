#pragma once

// Copy this file to firmware/field/include/espnow_secrets.h and
// firmware/gateway/include/espnow_secrets.h, then fill in the same values on
// both nodes. Never commit the real file.
//
// ESP-NOW encryption uses a 16-byte PMK (network key) and a 16-byte LMK
// (peer link key). Generate them with:
//     openssl rand -hex 16
//
// The gateway MAC can be read from the gateway's serial log on boot
// ("[gw] own MAC ..."), or from your router's client list.

#define ESPNOW_PMK {0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, \
                    0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF}
#define ESPNOW_LMK {0xFF, 0xEE, 0xDD, 0xCC, 0xBB, 0xAA, 0x99, 0x88, \
                    0x77, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11, 0x00}

// Replace with the gateway's station MAC. All-zero keeps discovery enabled.
#define FIELD_GATEWAY_MAC {0x24, 0x6F, 0x28, 0x00, 0x00, 0x00}
