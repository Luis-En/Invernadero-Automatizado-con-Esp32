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

## Two field nodes

The field firmware builds as two roles from the same sources:

| | Primary (`env:field`) | Secondary (`env:field_secondary`) |
|---|---|---|
| Device id | `field_primary` | `field_secondary` |
| Soil probes | 2 on GPIO34, GPIO35 | 4 on GPIO32, GPIO33, GPIO34, GPIO35 |
| BME280 | SCL GPIO32 / SDA GPIO33 | none |
| Actuators | 2 fans (16/17) + 2 humidifiers (18/19) + pump (21) | none |
| Camera AP | yes | no |
| ESP-NOW | unicast to the gateway MAC once learned | same |

The gateway forwards both nodes' telemetry to the Pi. The serial bridge merges
them into one 6-slot reading (primary slots 0-1, secondary slots 0-3 → slots
2-5) so the backend and dashboard keep their existing model.

Unicast: a field learns the gateway MAC from the first command it receives
(the Pi's periodic timesync) and from then on sends telemetry and photo
fragments unicast. ESP-NOW then ACKs and retransmits each frame, which is what
stops fragments from being lost at 50 m. Until the MAC is known it broadcasts.

## Soil calibration (3.3 V)

The probes are the capacitive v1.2 type, powered at 3.3 V. Each probe is
calibrated with two points: the ADC value in dry air and the ADC value in
water. The percentage is interpolated between them and clamped to 0–100.

Defaults are `dry=3400`, `wet=1600` (roughly 3.3 V dry and 1.6 V wet). Every
probe varies, so calibrate each one in place over the USB serial console
(115200 baud). Slots are `0..5` = A1, A2, A3, B1, B2, B3; on the primary only
slots 0–1 are wired, on the secondary slots 0–3.

```
CAL SHOW          # print current dry/wet per slot
CAL DRY 0         # probe 0 in dry air  -> capture dry point
CAL WET 0         # probe 0 in water    -> capture wet point
CAL SAVE          # persist all slots to NVS
CAL RESET         # restore the 3.3 V defaults (then CAL SAVE)
```

Procedure per probe: leave it in dry air, wait a few seconds, `CAL DRY <slot>`;
submerge it in water, wait, `CAL WET <slot>`; repeat for every slot; then
`CAL SAVE`. The values survive reboots in NVS.

## Pin map (primary)

| Function | GPIO | Notes |
|----------|------|-------|
| Soil A1 / A2 (primary) | 34 / 35 | ADC1 only (ADC2 is unusable with the radio) |
| BME280 SDA / SCL | 33 / 32 | I2C |
| Fan 1 / Fan 2 | 16 / 17 | relay, active high |
| Humidifier 1 / 2 | 18 / 19 | MOSFET, active high |
| Pump | 21 | relay/SSR, active high |
| Camera link | Wi-Fi AP `invernadero-campo` | camera POSTs to `http://192.168.4.1/photo` |

Secondary soil (`env:field_secondary`): A1..B1 on GPIO32, GPIO33, GPIO34, GPIO35.

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

## Photo forwarding

The camera POSTs a whole JPEG to the field node's soft AP; the field node then
re-emits it to the gateway as ESP-NOW fragments. Sending all ~80 fragments back
to back overruns the receiver and loses most of them, so the fragments are
spread over `FIELD_PHOTO_SEND_WINDOW_MS` (default 120 s): one fragment every
`window / total_chunks` milliseconds (~1.5 s for a VGA frame).

Two buffers are kept, so while one frame is being forwarded the next upload is
accepted into the other and queued behind it. The HTTP response is sent as soon
as the body is received, so a slow forward never blocks the camera.

Tune the window in `include/config.h`. A shorter window sends faster but is more
likely to drop fragments; a longer one is gentler on the link.

## Config transfer

The gateway splits the config JSON into ESP-NOW chunks followed by a commit
frame carrying the whole-document CRC16. The node reassembles, verifies and
only then calls `applyNewConfig()`, which also saves to NVS. A partial or
corrupt push is discarded and never reaches the actuators.
