#pragma once

// Field node configuration: identity, pin map and timing. Pin map mirrors
// config/actuators.yaml on the Raspberry Pi side:
//   fan_1 GPIO16, fan_2 GPIO17, humidifier_1 GPIO18, humidifier_2 GPIO19,
//   pump GPIO21.
//
// Soil sensors MUST use ADC1 pins (GPIO32-39) on the ESP32: ADC2 is shared
// with the Wi-Fi/ESP-NOW radio and returns garbage while the radio is up.

#define FIELD_FW_VERSION_MAJOR 1
#define FIELD_FW_VERSION_MINOR 0
#define FIELD_FW_VERSION_PATCH 0
#define FIELD_FW_VERSION "1.0.0"

#define FIELD_DEVICE_ID "field_esp32"

// ---------------------------------------------------------------------------
// Soil sensors (capacitive v1.2, analog out). Order matches A1,A2,A3,B1,B2,B3.
// ---------------------------------------------------------------------------
#define SOIL_PIN_A1 32
#define SOIL_PIN_A2 33
#define SOIL_PIN_A3 34
#define SOIL_PIN_B1 35
#define SOIL_PIN_B2 36
#define SOIL_PIN_B3 39

// Which soil probes are physically connected. Bit 0=A1, 1=A2, 2=A3, 3=B1,
// 4=B2, 5=B3. Unset bits are reported as invalid instead of being read from a
// floating pin. Default: only B1 (GPIO35, "D35") is wired, matching the
// current bench setup. Set to 0x3F (all) for the full 19 m greenhouse.
#ifndef FIELD_SOIL_MASK
#define FIELD_SOIL_MASK 0x08
#endif

// Diagnostic scan: read every ADC1 pin in SOIL_PINS regardless of the mask and
// report the raw value, so a probe can be located on the bench (find which pin
// shows a changing reading). Enable with -DFIELD_SOIL_SCAN=1.
#ifndef FIELD_SOIL_SCAN
#define FIELD_SOIL_SCAN 0
#endif

// ADC full scale on the ESP32 and how many samples to average per reading.
#define SOIL_ADC_MAX 4095
#define SOIL_SAMPLES 12
// A reading below this (or at rail) is treated as a disconnected sensor.
#define SOIL_ADC_MIN_VALID 200
#define SOIL_ADC_MAX_VALID 4050

// ---------------------------------------------------------------------------
// BME280 (I2C). On the ESP32 the default I2C pins are SDA=21/SDO, but GPIO21
// is used by the pump, so the bus is moved to 25/26 below.
// ---------------------------------------------------------------------------
#define FIELD_I2C_SDA 25
#define FIELD_I2C_SCL 26
#define FIELD_BME280_ADDR 0x76

// ---------------------------------------------------------------------------
// Actuators. active_high matches config/actuators.yaml.
// ---------------------------------------------------------------------------
#define ACT_PIN_FAN_1 16
#define ACT_PIN_FAN_2 17
#define ACT_PIN_HUMIDIFIER_1 18
#define ACT_PIN_HUMIDIFIER_2 19
#define ACT_PIN_PUMP 21

#define ACT_FAN_ACTIVE_HIGH 1
#define ACT_HUMIDIFIER_ACTIVE_HIGH 1
#define ACT_PUMP_ACTIVE_HIGH 1

// Safe boot state: everything OFF until a valid config is loaded.
#define ACTUATORS_FAILSAFE_OFF 1

// ---------------------------------------------------------------------------
// Timing. The intervals can be overridden from platformio.ini to speed up
// bench testing (see the field_bringup environment).
// ---------------------------------------------------------------------------
#ifndef FIELD_SAMPLE_INTERVAL_MS
#define FIELD_SAMPLE_INTERVAL_MS 10000UL      // read sensors every 10 s
#endif
#ifndef FIELD_TELEMETRY_INTERVAL_MS
#define FIELD_TELEMETRY_INTERVAL_MS 30000UL   // publish every 30 s (avg)
#endif
#define FIELD_HELLO_INTERVAL_MS 60000UL
// ESP-NOW and the Wi-Fi AP share one radio, so both must use the same channel.
// The gateway must be built with the matching FIELD_ESPNOW_CHANNEL.
#define FIELD_ESPNOW_CHANNEL 6
#define FIELD_WIFI_CHANNEL FIELD_ESPNOW_CHANNEL

// ---------------------------------------------------------------------------
// Camera Wi-Fi link. The ESP32-CAM connects to the AP this node raises and
// POSTs the JPEG to /photo. The node then forwards fragments over ESP-NOW.
// ---------------------------------------------------------------------------
#define FIELD_AP_SSID "invernadero-campo"
#define FIELD_AP_PASSWORD "invernadero123"   // >= 8 chars
#define FIELD_AP_CHANNEL 6
#define FIELD_AP_MAX_CLIENTS 2
#define FIELD_PHOTO_BUFFER_MAX 40960         // one VGA JPEG plus header room
#define FIELD_PHOTO_TCP_PORT 80

// Optional bench build: fake sensors, no BME280 required.
#ifndef FIELD_BENCH
#define FIELD_BENCH 0
#endif

#ifndef FIELD_NO_BME280
#define FIELD_NO_BME280 0
#endif

// Diagnostic build: print every photo chunk received from the camera over the
// USB serial port and skip ESP-NOW forwarding. Used to validate the camera ->
// field UART link on hardware without a gateway. Enable with -DFIELD_PHOTO_TEST=1.
#ifndef FIELD_PHOTO_TEST
#define FIELD_PHOTO_TEST 0
#endif
