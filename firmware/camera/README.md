# Camera node firmware (ESP32-CAM)

Captures a JPEG on an interval and uploads it over Wi-Fi to the field ESP32,
which forwards it to the gateway over ESP-NOW. No router is needed: the field
node raises its own access point and the camera joins it.

## Layout

```
camera/
├── platformio.ini
├── include/
│   ├── config.h            # Wi-Fi credentials, capture cadence, frame size
│   ├── camera_capture.h    # OV2640 init + capture
│   └── wifi_sender.h       # JPEG -> HTTP POST to the field node
└── src/
```

## Build and flash

```bash
cd firmware/camera
pio run -e camera              # compile
pio run -e camera -t upload    # flash using the micro-USB shield
pio device monitor             # 115200 baud
```

The AI-Thinker board has no USB; use the micro-USB shield. If the upload gets
stuck at `Connecting....`, hold **GPIO0 to GND** during reset.

## How it connects

1. Boots, joins the Wi-Fi network `invernadero-campo` (raised by the field node).
2. Waits 20 s, then captures the first JPEG and POSTs it to
   `http://192.168.4.1/photo`.
3. Repeats every 30 minutes.

The credentials and the field node address are in `include/config.h` and must
match `firmware/field/include/config.h` (`FIELD_AP_*`).

## Capture settings

| Setting | Value | Rationale |
|---------|-------|-----------|
| Resolution | VGA 640x480 | ~30 KB JPEG, uploads over Wi-Fi in a second |
| JPEG quality | 12 | good size/quality trade-off |
| Cadence | 30 min | matches the Pi backend default |
| First capture | 20 s after boot | lets the pipeline be verified quickly |

Without PSRAM the firmware falls back to QVGA so the node still produces
images.

## What the field node sees

The field node logs on its serial console:

```
[photo] frame 1 received over WiFi: 30022 bytes
[photo] frame 1 forwarded as 151 chunks
```

If the camera reports `upload FAILED`, check that the field node is powered and
that the SSID/password match.
