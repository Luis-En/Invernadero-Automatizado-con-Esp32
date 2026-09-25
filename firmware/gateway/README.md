# ESP32 / ESP8266 Gateway Firmware

ESP-NOW to USB serial bridge for the automated greenhouse. This node sits
between the field ESP32 and the Raspberry Pi 5:

```
[field ESP32] --ESP-NOW--> [gateway ESP32] --USB serial--> [RPi5 serial_bridge] --> FastAPI
[camera ESP32] --ESP-NOW-->       ^
                                  |
                        commands / config from the Pi
```

It does not read sensors itself. It receives binary ESP-NOW frames from the
field and camera nodes and re-emits them as JSON lines, so the Pi side never
has to parse the compact wire format.

## Build

Uses PlatformIO with the Arduino framework. Both ESP32 and ESP8266 are
supported; the same sources compile for each, only the transport differs.

| Environment | Board | Purpose |
|-------------|-------|---------|
| `gateway` | ESP32 DevKit (`esp32dev`) | Real gateway |
| `gateway_sim` | ESP32 DevKit | Bench build with synthetic field/camera |
| `gateway_esp8266` | NodeMCU (`nodemcuv2`) | Real gateway on ESP8266 |
| `gateway_esp8266_sim` | NodeMCU | Bench build on ESP8266 |

```bash
pio run -e gateway -t upload
pio run -e gateway_esp8266 -t upload
pio device monitor              # 115200 baud
```

The `*_sim` builds generate synthetic telemetry and photo chunks locally
(mirroring `backend/serial_bridge/simulator.py`), so a single board can drive
the full Pi pipeline without any other node connected:

```bash
pio run -e gateway_sim -t upload
pio run -e gateway_esp8266_sim -t upload
```

The telemetry and photo chunk serialization is shared (`src/json_builder.cpp`,
`src/serial_link.cpp`) with no platform branches, so both targets emit the
same JSON. The host test `scripts/check_payloads.sh` compiles that code for
the desktop and validates the output against the backend schema.

## Serial contract

Both directions use one line per message:

```
<json>*<CRC16 hex>\n
```

CRC16 is CRC-16/CCITT-FALSE (poly `0x1021`, init `0x0000`), the same value
Python computes with `binascii.crc_hqx(data, 0)`. The CRC covers the JSON
bytes only, not the `*`, the hex digits, or the newline. Lines without a `*`
suffix are accepted for manual debugging.

### Gateway to Pi

| `type` | Purpose | Fields |
|--------|---------|--------|
| `hello` | Boot and `ping` reply | `role`, `device_id`, `firmware`, `protocol`, `uptime_s`, `config_version`, `time_synced`, `simulate` |
| `telemetry` | Field reading, ready to POST to `/api/config/telemetry` | `timestamp`, `temperature`, `humidity`, `pressure`, `soil_adc[6]`, `soil_pct[6]`, `soil_ok[6]`, `fan_1_state`, `fan_2_state`, `humidifier_1_state`, `humidifier_2_state`, `pump_state`, `rssi`, `device_id`, `sequence` |
| `photo_chunk` | Camera chunk, ready to POST to `/api/photos/chunk` | `sequence`, `total_chunks`, `chunk_index`, `crc16`, `data` (hex), `device_id` |
| `device_status` | Heartbeat every 30s | `field_online`, `camera_online`, `field_rssi`, `camera_rssi`, `field_last_seen_s`, `camera_last_seen_s`, `config_version`, `uptime_s`, `free_heap`, `simulate` |
| `event` | Watchdog and fault notifications | `severity`, `code`, `message`, `timestamp` |
| `config_ack` | Result of a config push | `version`, `cmd`, `status` (`ok`/`error`), `message` |

The `telemetry` and `photo_chunk` payloads are field-for-field identical to
what `simulator.py` posts today, plus the `type` discriminator. The Pi bridge
can strip `type` and forward the rest unchanged.

### Pi to gateway

| `type` | Fields | Effect |
|--------|--------|--------|
| `set_config` | `version`, `config_json`, `target` | Chunked push to the field node over ESP-NOW, then a commit frame. The field applies only after a valid commit. |
| `timesync` | `epoch` | Sets the gateway clock, forwards to field and camera |
| `reboot` | `target` | `gateway` reboots locally, otherwise forwarded |
| `purge` | `target` | Forwarded, asks the node to drop buffered data |
| `ping` | none | Gateway replies with `hello` |

`target` accepts `field` (default), `camera` or `gateway`.

## ESP-NOW wire format

Packed binary structs, capped at 250 bytes per frame (ESP-NOW limit). The
field and camera firmware must use the same definitions in
`include/protocol.h`.

| Message | Struct | Size |
|---------|--------|------|
| `0x01` telemetry | `TelemetryMsg` | 42 B |
| `0x02` photo chunk | `PhotoChunkMsg` | 221 B |
| `0x03` command | `CommandMsg` | 185 B |
| `0x04` ack | `AckMsg` | 17 B |
| `0x05` hello | `HelloMsg` | 35 B |

Config documents larger than the 160 byte command payload are split into
`CMD_SET_CONFIG_CHUNK` frames, followed by `CMD_SET_CONFIG_COMMIT` carrying
the CRC16 of the full document in `arg`. The field replies with an `AckMsg`;
the gateway retries the commit up to 4 times before reporting
`CONFIG_TIMEOUT`.

## Behaviour

- The ESP-NOW layer is the shared driver in `../common` (`espnow_hal`). It
  hides the ESP32 (2.x and 3.x callback signatures) and ESP8266 (role setup,
  `bool` returns, `uint8_t` callbacks) differences. Received frames go into a
  ring buffer and are handled in `loop()`, never in the Wi-Fi callback.
- Peers are learned from traffic and stored by MAC in `DeviceRegistry`.
  Commands to an unknown node fall back to the ESP-NOW broadcast address.
- A field or camera node unseen for 5 minutes raises `FIELD_OFFLINE` /
  `CAMERA_OFFLINE`, matching the system watchdog.
- `rssi` comes from the ESP-NOW receive metadata on arduino-esp32 3.x. On
  arduino-esp32 2.x and on ESP8266 the Arduino callback does not expose it, so
  the field node reports its own value in the telemetry frame instead.
- Config version and the last known epoch survive reboots: `Preferences` on
  ESP32, the `EEPROM` emulation on ESP8266 (`src/state_store.cpp`).

## Wiring

The gateway only needs power and the USB link to the Pi. No sensors or
actuators are attached. USB serial is the UART bridge at 115200 baud, which
appears as `/dev/ttyUSB0` on the Pi (the `SERIAL_PORT` used by
`docker-compose.yml`). On ESP8266 use the NodeMCU USB port.

## Layout

```
include/config.h            build constants
include/protocol.h          wire structs, CRC16, serial contract (no Arduino deps)
include/json_builder.h      serial JSON document builders (shared, host-testable)
include/serial_link.h       JSON-lines framing and command parsing
include/device_registry.h   peer table, online/watchdog state
include/config_pusher.h     chunked config transfer to the field
include/simulator.h         bench-only synthetic source
include/state_store.h       persistence and gateway clock
src/main.cpp                wiring and main loop
../common/                  shared ESP-NOW HAL, button and LED drivers
```
