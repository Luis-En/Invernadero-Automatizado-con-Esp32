#pragma once

// Field node configuration: identity, pin map and timing. Pin map mirrors
// config/actuators.yaml on the Raspberry Pi side:
//   fan_1 GPIO16, fan_2 GPIO17, humidifier_1 GPIO18, humidifier_2 GPIO19,
//   pump GPIO21.
//
// Soil sensors MUST use ADC1 pins (GPIO32-39) on the ESP32: ADC2 is shared
// with the Wi-Fi/ESP-NOW radio and returns garbage while the radio is up.

#define FIELD_FW_VERSION_MAJOR 1
#define FIELD_FW_VERSION_MINOR 1
#define FIELD_FW_VERSION_PATCH 0
#define FIELD_FW_VERSION "1.1.0"

// Selects which of the two field nodes this build is. The primary owns the
// BME280, the actuators and the camera AP; the secondary only reads the extra
// soil probes and forwards them over ESP-NOW.
#ifndef FIELD_ROLE_SECONDARY
#define FIELD_ROLE_SECONDARY 0
#endif

#if FIELD_ROLE_SECONDARY
#define FIELD_DEVICE_ID "field_secondary"
#define FIELD_HAS_BME280 0
#define FIELD_HAS_ACTUATORS 0
#define FIELD_HAS_CAMERA_AP 0
#else
#define FIELD_DEVICE_ID "field_primary"
#define FIELD_HAS_BME280 1
#define FIELD_HAS_ACTUATORS 1
#define FIELD_HAS_CAMERA_AP 1
#endif

// ---------------------------------------------------------------------------
// Soil sensors (capacitive v1.2, analog out) on ADC1 only.
//
// Primary:   2 probes on GPIO34, GPIO35.
// Secondary: 4 probes on GPIO32, GPIO33, GPIO34, GPIO35.
//
// Slots are A1..A3, B1..B3. Only the ones in FIELD_SOIL_MASK are read; the
// rest are reported invalid instead of sampling a floating pin.
// ---------------------------------------------------------------------------
#if FIELD_ROLE_SECONDARY
#define SOIL_PIN_A1 32
#define SOIL_PIN_A2 33
#define SOIL_PIN_A3 34
#define SOIL_PIN_B1 35
#define SOIL_PIN_B2 36
#define SOIL_PIN_B3 39
#ifndef FIELD_SOIL_MASK
#define FIELD_SOIL_MASK 0x0F
#endif
#else
#define SOIL_PIN_A1 34
#define SOIL_PIN_A2 35
#define SOIL_PIN_A3 36
#define SOIL_PIN_B1 39
#define SOIL_PIN_B2 25
#define SOIL_PIN_B3 26
#ifndef FIELD_SOIL_MASK
#define FIELD_SOIL_MASK 0x03
#endif
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

// Default 2-point calibration for the capacitive v1.2 probe at 3.3 V:
// dry air ~3.3 V (ADC ~3400), water ~1.6 V (ADC ~1600). Every probe varies, so
// use the CAL commands over the USB serial to calibrate each one in place.
#define SOIL_CAL_DRY_DEFAULT 3400
#define SOIL_CAL_WET_DEFAULT 1600

// ---------------------------------------------------------------------------
// BME280 (primary only). SCL -> GPIO32, SDA -> GPIO33. The 6-pin module's
// CSB/SDO are assumed strapped on the board (CSB high = I2C, SDO low = 0x76);
// set the macros below to a GPIO if your breakout needs them driven.
// ---------------------------------------------------------------------------
#define FIELD_I2C_SDA 33
#define FIELD_I2C_SCL 32
#define FIELD_BME280_CSB_PIN -1
#define FIELD_BME280_SDO_PIN -1
#define FIELD_BME280_ADDR 0x76

// ---------------------------------------------------------------------------
// Actuators (primary only). active_high matches config/actuators.yaml.
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

// Spread each photo's ESP-NOW chunks over this window instead of bursting them
// back to back. A burst of ~80 frames overruns the receiver and loses most of
// them; pacing to one chunk every window/total ms keeps the radio healthy.
#define FIELD_PHOTO_SEND_WINDOW_MS 120000UL

// Optional bench build: fake sensors, no BME280 required.
#ifndef FIELD_BENCH
#define FIELD_BENCH 0
#endif

#ifndef FIELD_NO_BME280
#define FIELD_NO_BME280 (!FIELD_HAS_BME280)
#endif

// Diagnostic build: print every photo chunk received from the camera over the
// USB serial port and skip ESP-NOW forwarding. Used to validate the camera ->
// field UART link on hardware without a gateway. Enable with -DFIELD_PHOTO_TEST=1.
#ifndef FIELD_PHOTO_TEST
#define FIELD_PHOTO_TEST 0
#endif

// Calibration-only build: skip Wi-Fi/ESP-NOW entirely so a node on a weak USB
// supply (which browns out when the radio starts) can still boot and accept
// the CAL commands. Calibration lives in NVS and survives the reflash.
#ifndef FIELD_CALIBRATION_ONLY
#define FIELD_CALIBRATION_ONLY 0
#endif
