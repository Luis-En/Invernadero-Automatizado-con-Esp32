# Field node firmware (ESP32)

Reads the 6 capacitive soil probes and the BME280, drives the 5 actuators and
runs the automation/fail-safe loop. Because the control logic lives here, the
greenhouse keeps working when the gateway or the Raspberry Pi go down: the last
valid configuration is stored in NVS and reloaded on boot.

## Layout

```
field/
├── platformio.ini          # field and field_bench environments
├── include/
│   ├── config.h            # pins, timing, identity
│   ├── config_model.h      # RuntimeConfig + JSON parsing + CRC
│   ├── automation.h        # C++ port of backend/api/app/automation.py
│   ├── sensors.h           # soil ADC + BME280
│   ├── actuators.h         # 5 output pins
│   ├── persistence.h       # NVS (Preferences) config + calibration
│   ├── field_link.h        # ESP-NOW commands / telemetry / config push
│   └── photo_link.h        # camera UART -> ESP-NOW photo forwarding
├── src/                    # one .cpp per header
└── tools/
    ├── Arduino.h           # host shim for the logic tests
    ├── logic_tests.cpp     # mirrors backend tests/test_automation.py
    └── run_logic_tests.sh
```

## Pin map

| Function | GPIO | Notes |
|----------|------|-------|
| Soil A1..A3 | 32, 33, 34 | ADC1 only (ADC2 is unusable with the radio) |
| Soil B1..B3 | 35, 36, 39 | ADC1 only |
| BME280 SDA / SCL | 25 / 26 | I2C |
| Fan 1 / Fan 2 | 16 / 17 | relay, active high |
| Humidifier 1 / 2 | 18 / 19 | MOSFET, active high |
| Pump | 21 | relay/SSR, active high |
| Camera UART RX / TX | 13 / 4 | to the ESP32-CAM |

See `config/actuators.yaml` on the Pi for the matching logical definition.

## Build and flash

```bash
cd firmware/field

pio run -e field              # compile for the real board
pio run -e field -t upload    # flash
pio device monitor            # 115200 baud

pio run -e field_bench        # bench build: no BME280, synthetic temperature
```

If PlatformIO is not on your PATH, the VS Code task **Firmware: build field**
runs the same command through the PlatformIO IDE extension. See
`docs/vscode-setup.md`.

## Host logic tests

The automation and config parsing are compiled for the host and asserted
against the same cases as the backend:

```bash
cd firmware/field
pio run -e field              # once, to fetch ArduinoJson
bash tools/run_logic_tests.sh
```

## Safety model

1. **Fail-safe boot.** `actuators.begin()` forces every output to OFF before
   anything else runs. Nothing turns on until a valid config is loaded.
2. **Invalid readings.** A missing or out-of-range temperature/humidity/soil
   sample forces the related actuator OFF. A disconnected probe can never hold
   the pump on.
3. **Hysteresis.** Each actuator has distinct ON/OFF thresholds, identical to
   the Python implementation in `backend/api/app/automation.py`.
4. **Maximum ON time.** Fans/humidifiers 2 h and the pump 15 min by default,
   configurable from the Pi inside `safety.max_on_seconds`.
5. **Irrigation off by default.** The pump only runs when the config says
   `irrigation.enabled = true`.
6. **Config integrity.** A pushed config is applied and persisted only after
   the commit frame's CRC matches the reassembled document and the thresholds
   pass validation.

## Config transfer

The gateway splits the config JSON into ESP-NOW chunks followed by a commit
frame carrying the whole-document CRC16. The node reassembles, verifies and
only then calls `applyNewConfig()`, which also saves to NVS. A partial or
corrupt push is discarded and never reaches the actuators.
