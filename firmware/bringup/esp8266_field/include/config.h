#pragma once

// ESP8266 field bring-up node. One capacitive soil moisture sensor on A0.
//
// The NodeMCU/Wemos A0 input has an on-board divider so 0-3.3 V maps to the
// ADC range 0-1023. The capacitive probe output is 0-3.0 V, so it connects
// directly. Calibrate by noting the raw value in dry air and in a cup of water.

#define FIELD_FW_VERSION "0.1.0-bringup"
#define FIELD_DEVICE_ID "field_esp8266"

// ADC range for the ESP8266. analogRead() returns 0..1023.
#define SOIL_ADC_MAX 1023

// Two-point calibration for the soil probe. These defaults are a rough starting
// point; run the calibration commands below to replace them:
//   send "cal dry"  while the probe is in dry air
//   send "cal wet"  while the probe is in water
// The raw value is HIGH when dry and LOW when wet.
#define SOIL_DRY_DEFAULT 800
#define SOIL_WET_DEFAULT 350

// Publish interval. Telemetry is also sent immediately after calibration.
#define TELEMETRY_INTERVAL_MS 10000UL
#define HELLO_INTERVAL_MS 30000UL

#define ESPNOW_CHANNEL_DEFAULT 1

// Capacitive probes are noisy: average several samples and drop the extremes.
#define SOIL_SAMPLES 15
