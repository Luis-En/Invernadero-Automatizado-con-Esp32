#include <Arduino.h>
#include <Wire.h>

// Definitive single-bus probe. Reports the idle line levels (to tell whether
// the module provides pull-ups), then scans the BME280 addresses at both a slow
// and the default clock with the internal pull-ups enabled.

#ifndef I2C_PROBE_SDA
#define I2C_PROBE_SDA 2
#endif
#ifndef I2C_PROBE_SCL
#define I2C_PROBE_SCL 15
#endif

namespace {
const uint8_t kAddresses[] = {0x76, 0x77};

void reportIdle(const char* label, int mode) {
  pinMode(I2C_PROBE_SDA, mode);
  pinMode(I2C_PROBE_SCL, mode);
  delay(5);
  Serial.printf("  idle %-14s SDA=%d SCL=%d\n", label, digitalRead(I2C_PROBE_SDA),
                digitalRead(I2C_PROBE_SCL));
}

void scan(const char* label, uint32_t hz) {
  Wire.begin(I2C_PROBE_SDA, I2C_PROBE_SCL, hz);
  Wire.setTimeOut(30);
  delay(20);
  Serial.printf("  scan %-10s @%uHz:", label, (unsigned)hz);
  for (uint8_t addr : kAddresses) {
    Wire.beginTransmission(addr);
    uint8_t rc = Wire.endTransmission();
    Serial.printf(" 0x%02X=rc%u%s", addr, rc, rc == 0 ? "*" : "");
  }
  Serial.println();
  Wire.end();
  delay(20);
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.printf("=== BME280 definitive probe SDA=%d SCL=%d ===\n", I2C_PROBE_SDA,
                I2C_PROBE_SCL);

  // 6-pin module: CSB high selects I2C. Drive both strap candidates high.
  pinMode(4, OUTPUT);
  digitalWrite(4, HIGH);
  pinMode(14, OUTPUT);
  digitalWrite(14, HIGH);
  delay(30);

  reportIdle("floating", INPUT);
  reportIdle("pull-up", INPUT_PULLUP);

  scan("slow", 10000);
  scan("normal", 100000);

  Serial.println("=== probe done ===");
}

void loop() { delay(1000); }
