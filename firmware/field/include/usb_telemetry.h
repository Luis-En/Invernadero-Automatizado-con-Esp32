#pragma once

#include "protocol.h"

// Emits the same JSON telemetry line the gateway would send, directly on the
// field node's USB serial port. This lets the Raspberry Pi bridge read the
// field node on its own, without a gateway, while the ESP-NOW link is still
// being brought up.
//
// The line is framed exactly like the gateway protocol so the existing
// gateway_protocol.py parser accepts it:
//     <json>*<CRC16 hex>\n
namespace usb_telemetry {

void emit(const TelemetryData& telemetry);

}  // namespace usb_telemetry
