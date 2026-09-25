#include <Arduino.h>

#include "config.h"
#include "config_pusher.h"
#include "device_registry.h"
#include "espnow_hal.h"
#include "protocol.h"
#include "serial_link.h"
#include "state_store.h"

#if GW_SIMULATE
#include "simulator.h"
#endif

namespace {
bool field_was_online = false;
bool camera_was_online = false;
uint32_t last_heartbeat_ms = 0;
uint32_t boot_ms = 0;

#if GW_SIMULATE
uint16_t sim_photo_sequence = 0;
uint16_t sim_photo_total = 0;
uint16_t sim_photo_index = 0;
#endif

void fillHeader(EspNowHeader& header, uint8_t type) {
  header.magic = ESPNOW_MAGIC;
  header.version = ESPNOW_PROTO_VERSION;
  header.type = type;
  memcpy(header.src, espNow.ownMac(), 6);
  header.seq = espNow.nextSeq();
}

void sendCommand(uint8_t targetRole, uint8_t command, uint16_t version, uint32_t arg) {
  uint8_t mac[6];
  if (!registry.macForRole(targetRole, mac)) {
    memcpy(mac, ESPNOW_BROADCAST_MAC, 6);
  }

  CommandMsg msg;
  memset(&msg, 0, sizeof(msg));
  fillHeader(msg.hdr, MSG_COMMAND);
  msg.cmd = command;
  msg.version = version;
  msg.arg = arg;

  espNow.send(mac, (const uint8_t*)&msg, sizeof(msg));
}

void onConfigResult(bool ok, uint16_t version) {
  if (ok) {
    state.setConfigVersion(version);
    serialLink.sendConfigAck(version, CMD_SET_CONFIG_COMMIT, 0, "applied by field node");
    serialLink.sendEvent("info", "CONFIG_APPLIED", "Field node confirmed the new configuration");
  } else {
    serialLink.sendConfigAck(version, CMD_SET_CONFIG_COMMIT, 1, "field node did not acknowledge");
    serialLink.sendEvent("warning", "CONFIG_TIMEOUT", "Field node did not confirm the configuration");
  }
}

void onInboundCommand(const InboundCommand& command) {
  switch (command.kind) {
    case InboundKind::SetConfig: {
      uint16_t version = command.version != 0 ? command.version : (state.configVersion() + 1);
      uint8_t mac[6];
      if (!registry.macForRole(command.target, mac)) {
        memcpy(mac, ESPNOW_BROADCAST_MAC, 6);
      }
      if (!configPusher.start(version, command.config_json, mac)) {
        serialLink.sendConfigAck(version, CMD_SET_CONFIG_COMMIT, 1, "empty configuration");
      }
      break;
    }
    case InboundKind::Timesync:
      state.syncEpoch(command.epoch);
      sendCommand(ROLE_FIELD, CMD_TIMESYNC, 0, command.epoch);
      sendCommand(ROLE_CAMERA, CMD_TIMESYNC, 0, command.epoch);
      // Do not answer with a hello here: the bridge sends a timesync in reply
      // to every hello, so replying would create an endless hello/timesync
      // loop that floods the serial port.
      break;
    case InboundKind::Reboot:
      if (command.target == ROLE_GATEWAY) {
        serialLink.sendEvent("info", "GATEWAY_REBOOT", "Rebooting gateway on request");
        delay(100);
        ESP.restart();
      }
      sendCommand(command.target, CMD_REBOOT, 0, 0);
      break;
    case InboundKind::Purge:
      sendCommand(command.target, CMD_PURGE, 0, 0);
      break;
    case InboundKind::Ping:
      serialLink.sendHello();
      break;
    default:
      serialLink.sendEvent("warning", "CMD_UNKNOWN", "Unrecognized serial command");
      break;
  }
}

void handleTelemetry(const EspNowMessage& frame) {
  TelemetryMsg msg;
  memcpy(&msg, frame.data, sizeof(msg));

  TelemetryData telemetry;
  decodeTelemetry(msg, frame.rssi, telemetry);

  const char* known = registry.deviceIdForRole(ROLE_FIELD);
  const char* deviceId = (known != nullptr && known[0] != '\0') ? known : "field_esp32";
  strncpy(telemetry.device_id, deviceId, sizeof(telemetry.device_id) - 1);
  telemetry.device_id[sizeof(telemetry.device_id) - 1] = '\0';

  registry.update(frame.mac, ROLE_FIELD, telemetry.device_id, frame.rssi, state.now());
  serialLink.sendTelemetry(telemetry);

#if GW_DEBUG_PEERS
  // Bring-up diagnostic: show exactly which MAC sent each telemetry frame, its
  // RSSI and every raw soil ADC value, so a probe can be located and a missing
  // sender is obvious on the serial monitor.
  Serial.printf(
      "# [gw] telemetry from %02X:%02X:%02X:%02X:%02X:%02X rssi=%d temp=%.1f "
      "adc=[%u,%u,%u,%u,%u,%u] ok=[%d,%d,%d,%d,%d,%d]\n",
      frame.mac[0], frame.mac[1], frame.mac[2], frame.mac[3], frame.mac[4],
      frame.mac[5], (int)frame.rssi, telemetry.temperature,
      (unsigned)telemetry.soil[0].adc, (unsigned)telemetry.soil[1].adc,
      (unsigned)telemetry.soil[2].adc, (unsigned)telemetry.soil[3].adc,
      (unsigned)telemetry.soil[4].adc, (unsigned)telemetry.soil[5].adc,
      (int)telemetry.soil[0].ok, (int)telemetry.soil[1].ok,
      (int)telemetry.soil[2].ok, (int)telemetry.soil[3].ok,
      (int)telemetry.soil[4].ok, (int)telemetry.soil[5].ok);
#endif
}

void handlePhotoChunk(const EspNowMessage& frame) {
  PhotoChunkMsg msg;
  memcpy(&msg, frame.data, sizeof(msg));

  PhotoChunkData chunk;
  decodePhotoChunk(msg, chunk);
  strncpy(chunk.device_id, "camera", sizeof(chunk.device_id) - 1);

  registry.update(frame.mac, ROLE_CAMERA, chunk.device_id, frame.rssi, state.now());
  serialLink.sendPhotoChunk(chunk);
}

void handleHello(const EspNowMessage& frame) {
  HelloMsg msg;
  memcpy(&msg, frame.data, sizeof(msg));

  char deviceId[17];
  memcpy(deviceId, msg.device_id, sizeof(msg.device_id));
  deviceId[sizeof(msg.device_id)] = '\0';

  registry.update(frame.mac, msg.role, deviceId, frame.rssi, state.now());
}

void handleAck(const EspNowMessage& frame) {
  AckMsg msg;
  memcpy(&msg, frame.data, sizeof(msg));
  configPusher.onAck(msg.cmd, msg.status, msg.version);
}

void handleEvent(const EspNowMessage& frame) {
  EventMsg msg;
  memcpy(&msg, frame.data, sizeof(msg));

  char code[25];
  char message[65];
  memcpy(code, msg.code, sizeof(msg.code));
  code[sizeof(msg.code)] = '\0';
  memcpy(message, msg.message, sizeof(msg.message));
  message[sizeof(msg.message)] = '\0';

  const char* severity = "info";
  if (msg.severity == 1) {
    severity = "warning";
  } else if (msg.severity >= 2) {
    severity = "critical";
  }

  // Forward as a backend event so it shows in the web Events page.
  serialLink.sendEvent(severity, code, message);

#if GW_DEBUG_PEERS
  Serial.printf("# [gw] event from %02X:%02X:%02X:%02X:%02X:%02X rssi=%d %s: %s\n",
                frame.mac[0], frame.mac[1], frame.mac[2], frame.mac[3], frame.mac[4],
                frame.mac[5], (int)frame.rssi, code, message);
#endif
}

void handleFrame(const EspNowMessage& frame) {
  if (frame.length < sizeof(EspNowHeader)) {
    return;
  }
  EspNowHeader header;
  memcpy(&header, frame.data, sizeof(header));
  if (header.magic != ESPNOW_MAGIC || header.version != ESPNOW_PROTO_VERSION) {
    return;
  }

  switch (header.type) {
    case MSG_TELEMETRY:
      if (frame.length >= sizeof(TelemetryMsg)) {
        handleTelemetry(frame);
      }
      break;
    case MSG_PHOTO_CHUNK:
      if (frame.length >= sizeof(PhotoChunkMsg)) {
        handlePhotoChunk(frame);
      }
      break;
    case MSG_HELLO:
      if (frame.length >= sizeof(HelloMsg)) {
        handleHello(frame);
      }
      break;
    case MSG_ACK:
      if (frame.length >= sizeof(AckMsg)) {
        handleAck(frame);
      }
      break;
    case MSG_EVENT:
      if (frame.length >= sizeof(EventMsg)) {
        handleEvent(frame);
      }
      break;
    default:
      break;
  }
}

DeviceStatus buildStatus() {
  DeviceStatus status;
  uint32_t nowMs = millis();
  status.field_online = registry.isOnline(ROLE_FIELD, nowMs, GW_DEVICE_TIMEOUT_MS);
  status.camera_online = registry.isOnline(ROLE_CAMERA, nowMs, GW_DEVICE_TIMEOUT_MS);
  status.field_rssi = registry.rssiForRole(ROLE_FIELD);
  status.camera_rssi = registry.rssiForRole(ROLE_CAMERA);
  status.field_last_seen_s = registry.secondsSinceSeen(ROLE_FIELD, nowMs);
  status.camera_last_seen_s = registry.secondsSinceSeen(ROLE_CAMERA, nowMs);
  status.config_version = state.configVersion();
  status.uptime_s = (nowMs - boot_ms) / 1000UL;
  status.free_heap = ESP.getFreeHeap();
  status.simulate = GW_SIMULATE != 0;
  return status;
}

void tickHeartbeat() {
  if (millis() - last_heartbeat_ms < GW_HEARTBEAT_INTERVAL_MS) {
    return;
  }
  last_heartbeat_ms = millis();
  serialLink.sendDeviceStatus(buildStatus());

  bool fieldOnline = registry.isOnline(ROLE_FIELD, millis(), GW_DEVICE_TIMEOUT_MS);
  if (field_was_online && !fieldOnline) {
    serialLink.sendEvent("critical", "FIELD_OFFLINE", "Field ESP32 not seen for over 5 minutes");
  } else if (!field_was_online && fieldOnline) {
    serialLink.sendEvent("info", "FIELD_ONLINE", "Field ESP32 is online");
  }
  field_was_online = fieldOnline;

  bool cameraOnline = registry.isOnline(ROLE_CAMERA, millis(), GW_DEVICE_TIMEOUT_MS);
  if (camera_was_online && !cameraOnline) {
    serialLink.sendEvent("warning", "CAMERA_OFFLINE", "Camera not seen for over 5 minutes");
  } else if (!camera_was_online && cameraOnline) {
    serialLink.sendEvent("info", "CAMERA_ONLINE", "Camera is online");
  }
  camera_was_online = cameraOnline;
}

#if GW_SIMULATE
void tickSimulator() {
  if (simulator.dueTelemetry(millis())) {
    TelemetryData telemetry = simulator.nextTelemetry();
    strncpy(telemetry.device_id, "field_esp32", sizeof(telemetry.device_id) - 1);
    serialLink.sendTelemetry(telemetry);
  }

  if (simulator.duePhoto(millis())) {
    simulator.beginPhoto();
    sim_photo_sequence = simulator.nextPhotoSequence();
    sim_photo_total = simulator.photoChunkCount();
    sim_photo_index = 0;
  }

  if (sim_photo_index < sim_photo_total) {
    PhotoChunkData chunk = simulator.nextPhotoChunk(sim_photo_sequence, sim_photo_index);
    strncpy(chunk.device_id, "camera", sizeof(chunk.device_id) - 1);
    serialLink.sendPhotoChunk(chunk);
    sim_photo_index++;
  }
}
#endif

}  // namespace

void setup() {
  serialLink.begin(GW_SERIAL_BAUD);
  delay(200);
  boot_ms = millis();

  state.begin();
  registry.begin();
  if (!espNow.begin(GW_WIFI_CHANNEL)) {
    serialLink.sendEvent("critical", "ESPNOW_INIT", "ESP-NOW initialization failed");
  }

  configPusher.begin(&espNow);
  configPusher.setResultCallback(onConfigResult);
  serialLink.setCommandCallback(onInboundCommand);

#if GW_SIMULATE
  simulator.begin(GW_SIM_TELEMETRY_INTERVAL_SEC, GW_SIM_PHOTO_INTERVAL_SEC);
#endif

  serialLink.sendHello();
  serialLink.sendEvent("info", "GATEWAY_BOOT", "Gateway started");
}

void loop() {
  serialLink.poll();

  EspNowMessage frame;
  while (espNow.poll(frame, 0)) {
    handleFrame(frame);
  }

  configPusher.tick();

#if GW_SIMULATE
  tickSimulator();
#endif

  tickHeartbeat();
  delay(2);
}
