# ESP-NOW Button / LED Link Test

Minimal link test for the ESP-NOW radios. Press the button on one board and
the LED toggles on the other, in both directions. The same source builds for
ESP32 and ESP8266, so the two can be mixed.

## Build and flash

```bash
pio run -e esp32 -t upload     # ESP32 DevKit
pio run -e esp8266 -t upload   # NodeMCU / Wemos D1 mini
pio device monitor             # 115200 baud, shows the MAC and each press
```

Both boards must run the same channel (`ESPNOW_CHANNEL`, default 1) and be in
range. No pairing is needed: press events are broadcast, so any board running
this sketch will toggle its LED on any press it hears.

## Default pins

| Board | Button | LED | LED active |
|-------|--------|-----|-----------|
| ESP32 DevKit | GPIO0 (BOOT) | GPIO2 | high |
| ESP8266 NodeMCU | GPIO0 (FLASH) | GPIO2 | low |

Override them from `platformio.ini` with build flags, for example:

```ini
build_flags = -DPIN_BUTTON=4 -DPIN_LED=5 -DLED_ACTIVE_LOW=0 -DESPNOW_CHANNEL=6
```

## How it works

- On a debounced press the board broadcasts a 2 byte `PressEvent` (magic plus
  an incrementing sequence) to `FF:FF:FF:FF:FF:FF`.
- On receive, the board ignores repeats by sequence and toggles its LED.
- Frames are queued from the Wi-Fi callback and handled in `loop()`.

## Shared drivers

The sketch uses the cross-platform drivers in `../common`:

- `espnow_hal` hides the ESP32 (2.x and 3.x callback signatures) and ESP8266
  (role setup, `bool` returns, `uint8_t` callbacks) API differences.
- `button` is a debounced active-low input with the internal pull-up.
- `led` handles active-high and active-low wiring.
- `board.h` holds the per-platform pin defaults.

The gateway firmware currently ships its own ESP-NOW layer because it needs
RSSI and a larger protocol; these drivers are the reusable base for the field,
camera and test nodes.
