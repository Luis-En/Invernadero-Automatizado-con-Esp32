# Serial Bridge

Reads the ESP32 gateway over USB serial and forwards its messages to the
FastAPI backend. It has two sources, selected with `SIMULATE`:

| Mode | `SIMULATE` | Source |
|------|-----------|--------|
| Simulation | `true` (default) | `simulator.py`, synthetic field node |
| Serial | `false` | ESP32 gateway on `SERIAL_PORT` |

## Serial mode

```bash
SIMULATE=false SERIAL_PORT=/dev/ttyUSB0 SERIAL_BAUDRATE=115200 \
API_URL=http://localhost:8000 python bridge.py
```

With Docker, the base compose file stays in simulation. Use the serial
override to attach the device:

```bash
SERIAL_DEVICE=/dev/ttyUSB0 docker compose \
  -f docker-compose.yml -f docker-compose.serial.yml up -d serial-bridge
```

The bridge parses one message per line, verifies the CRC16 and forwards:

| Gateway message | Action |
|-----------------|--------|
| `telemetry` | `POST /api/config/telemetry` |
| `photo_chunk` | `POST /api/photos/chunk` (hex decoded to bytes) |
| `hello` | Logged, then the bridge sends a `timesync` line back |
| `event` | Logged as a warning |
| `device_status` | Logged |
| `config_ack` | Logged |

Lines are `<json>*<CRC16 hex>\n`, with CRC-16/CCITT-FALSE. See
`gateway_protocol.py`. The reader runs in a background thread with automatic
reconnection, so unplugging the gateway does not kill the bridge.

Commands back to the gateway (`timesync`, and later `set_config`/`purge`) are
written on the same port.

## Files

```
bridge.py            entrypoint, source selection, API posting
serial_source.py     threaded pyserial reader with reconnect
gateway_protocol.py  CRC16 and line framing
simulator.py         synthetic field node for SIMULATE mode
```
