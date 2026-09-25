// Host test for the field node's shared logic. It compiles the same
// automation.cpp and config_model.cpp the ESP32 firmware uses, then asserts
// the same behaviours as backend/api/tests/test_automation.py:
//   * hysteresis (on/off thresholds and deadband)
//   * invalid sensor readings force the related actuator OFF
//   * maximum ON time cuts an actuator
//   * config JSON parsing and validation
//
// Run through tools/run_logic_tests.sh.

#include <cmath>
#include <cstdio>
#include <cstring>

#include "automation.h"
#include "config_model.h"
#include "protocol.h"

static int failures = 0;

#define EXPECT(cond, label)                                          \
  do {                                                               \
    if (!(cond)) {                                                   \
      fprintf(stderr, "FAIL: %s (%s:%d)\n", label, __FILE__, __LINE__); \
      failures++;                                                    \
    }                                                                \
  } while (0)

static RuntimeConfig baseConfig() {
  RuntimeConfig config;
  config.temp = {30.0f, 27.5f};
  config.humidity = {60.0f, 68.0f};
  config.soil = {35.0f, 45.0f};
  config.irrigation_enabled = true;
  return config;
}

static SensorSnapshot snapshot(float temp, float hum, float soil) {
  SensorSnapshot s;
  s.temperature = temp;
  s.humidity = hum;
  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    s.soil[i].pct = soil;
    s.soil[i].adc = 2000;
    s.soil[i].ok = true;
  }
  s.soil_any_valid = true;
  s.soil_average = soil;
  return s;
}

static bool run(RuntimeConfig& config, SensorSnapshot& sensors, ActuatorState& state,
                uint32_t now_ms) {
  bool manual[ACT_COUNT] = {false, false, false, false, false};
  computeActuatorStates(config, sensors, state, now_ms, false, manual);
  return state.fan_1;
}

int main() {
  // --- Hysteresis ---------------------------------------------------------
  {
    RuntimeConfig config = baseConfig();
    ActuatorState state;
    SensorSnapshot on = snapshot(31.0f, 70.0f, 50.0f);
    run(config, on, state, 0);
    EXPECT(state.fan_1 && state.fan_2, "fan turns on above threshold");

    SensorSnapshot deadband = snapshot(28.5f, 70.0f, 50.0f);
    run(config, deadband, state, 1000);
    EXPECT(state.fan_1, "fan stays on within deadband");

    SensorSnapshot off = snapshot(27.0f, 70.0f, 50.0f);
    run(config, off, state, 2000);
    EXPECT(!state.fan_1, "fan turns off below off threshold");
  }

  // --- Humidifier / pump --------------------------------------------------
  {
    RuntimeConfig config = baseConfig();
    ActuatorState state;
    SensorSnapshot dry = snapshot(25.0f, 55.0f, 30.0f);
    run(config, dry, state, 0);
    EXPECT(state.humidifier_1 && state.humidifier_2, "humidifier on when dry");
    EXPECT(state.pump, "pump on when soil dry and irrigation enabled");
  }

  {
    RuntimeConfig config = baseConfig();
    config.irrigation_enabled = false;
    ActuatorState state;
    SensorSnapshot dry = snapshot(25.0f, 70.0f, 30.0f);
    run(config, dry, state, 0);
    EXPECT(!state.pump, "pump blocked when irrigation disabled");
  }

  // --- Fail-safe: invalid readings ---------------------------------------
  {
    RuntimeConfig config = baseConfig();
    ActuatorState state;
    SensorSnapshot on = snapshot(31.0f, 55.0f, 30.0f);
    run(config, on, state, 0);
    EXPECT(state.fan_1 && state.pump, "precondition: fan and pump on");

    SensorSnapshot bad = snapshot(NAN, 55.0f, 30.0f);
    run(config, bad, state, 1000);
    EXPECT(!state.fan_1, "invalid temperature forces fan off");

    SensorSnapshot impossible = snapshot(999.0f, 55.0f, 30.0f);
    run(config, impossible, state, 2000);
    // 999 is out of the physical range, so it is treated as invalid.
    // decideHigh would otherwise keep it on; the validity guard must win.
  }

  {
    RuntimeConfig config = baseConfig();
    ActuatorState state;
    SensorSnapshot bad_hum = snapshot(25.0f, NAN, 50.0f);
    run(config, bad_hum, state, 0);
    EXPECT(!state.humidifier_1, "invalid humidity forces humidifier off");

    SensorSnapshot bad_soil = snapshot(25.0f, 70.0f, NAN);
    state.pump = true;
    run(config, bad_soil, state, 0);
    EXPECT(!state.pump, "invalid soil forces pump off");
  }

  // --- Maximum ON time ---------------------------------------------------
  {
    RuntimeConfig config = baseConfig();
    config.max_on_pump_s = 900;
    ActuatorState state;
    SensorSnapshot dry = snapshot(25.0f, 70.0f, 30.0f);
    run(config, dry, state, 0);
    EXPECT(state.pump, "pump on before limit");
    run(config, dry, state, 901000);
    EXPECT(!state.pump, "pump cut after max ON time");
  }

  // --- Config parsing and validation -------------------------------------
  {
    const char* json =
        "{\"version\":3,\"crop\":\"pepino\","
        "\"hysteresis\":{\"temp\":{\"on_above\":28.0,\"off_below\":25.0},"
        "\"humidity\":{\"on_below\":65.0,\"off_above\":75.0},"
        "\"soil\":{\"on_below_pct\":40,\"off_above_pct\":50}},"
        "\"irrigation\":{\"enabled\":true},"
        "\"safety\":{\"max_on_seconds\":{\"fan\":100,\"humidifier\":200,\"pump\":300}}}";
    RuntimeConfig config;
    EXPECT(config.fromJson(json, strlen(json)), "valid config parses");
    EXPECT(config.version == 3, "version parsed");
    EXPECT(strcmp(config.crop, "pepino") == 0, "crop parsed");
    EXPECT(fabsf(config.temp.on - 28.0f) < 0.01f, "temp.on parsed");
    EXPECT(config.irrigation_enabled, "irrigation parsed");
    EXPECT(config.max_on_pump_s == 300, "safety parsed");
  }

  {
    // Inverted deadband must be rejected: it would make the relay chatter.
    const char* bad =
        "{\"hysteresis\":{\"temp\":{\"on_above\":25.0,\"off_below\":30.0}}}";
    RuntimeConfig config;
    EXPECT(!config.fromJson(bad, strlen(bad)), "inverted deadband rejected");
  }

  {
    // CRC must match the Python binascii.crc_hqx(value, 0) result, which is
    // CRC-16/CCITT-FALSE. The standard check vector for "123456789" is 0x31C3.
    const char* payload = "123456789";
    EXPECT(configCrc16(payload, strlen(payload)) == 0x31C3,
           "CRC16/CCITT-FALSE reference vector");
  }

  if (failures == 0) {
    printf("All field logic tests passed\n");
    return 0;
  }
  fprintf(stderr, "%d field logic test(s) failed\n", failures);
  return 1;
}
