#pragma once

// Board defaults for the shared drivers. Override any of these with
// -DPIN_BUTTON=... / -DPIN_LED=... / -DLED_ACTIVE_LOW=... in platformio.ini.

#if defined(ESP8266)
// NodeMCU / Wemos D1 mini: onboard LED on GPIO2 (active low), FLASH button on GPIO0.
#ifndef PIN_BUTTON
#define PIN_BUTTON 0
#endif
#ifndef PIN_LED
#define PIN_LED 2
#endif
#ifndef LED_ACTIVE_LOW
#define LED_ACTIVE_LOW 1
#endif

#elif defined(ESP32)
// ESP32 DevKit: onboard LED on GPIO2 (active high), BOOT button on GPIO0.
#ifndef PIN_BUTTON
#define PIN_BUTTON 0
#endif
#ifndef PIN_LED
#define PIN_LED 2
#endif
#ifndef LED_ACTIVE_LOW
#define LED_ACTIVE_LOW 0
#endif

#else
#error "board.h only supports ESP32 and ESP8266 targets"
#endif

#ifndef ESPNOW_CHANNEL
#define ESPNOW_CHANNEL 1
#endif
