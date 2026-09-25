// Minimal Arduino shim so the field node's automation and config logic can be
// compiled and tested on a host, where the real framework is not available.
// Only the symbols those translation units actually use are provided.
#pragma once

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

typedef std::string String;

#ifndef HIGH
#define HIGH 1
#define LOW 0
#endif

inline void pinMode(int, int) {}
inline void digitalWrite(int, int) {}
inline int analogRead(int) { return 0; }
inline void analogReadResolution(int) {}
inline uint32_t millis() { return 0; }
inline void delay(uint32_t) {}

// Field config headers reference these; keep them harmless on the host.
#ifndef FIELD_BENCH
#define FIELD_BENCH 0
#endif
#ifndef FIELD_NO_BME280
#define FIELD_NO_BME280 1
#endif
