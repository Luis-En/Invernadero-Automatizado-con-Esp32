# ESP8266 bring-up firmware.

Two boards, matching the hardware being tested one component at a time:

* esp8266_field   - reads the soil moisture sensor on A0 and sends telemetry to
                    the gateway over ESP-NOW.
* esp8266_gateway - receives ESP-NOW telemetry and forwards it to the PC over
                    USB serial, using the same JSON+CRC line protocol the
                    Raspberry Pi bridge expects.

Both share firmware/common (ESP-NOW HAL + protocol). Build with:
    pio run -e field
    pio run -e gateway
