#pragma once

#include <Arduino.h>

#include "config.h"
#include "config_model.h"
#include "espnow_hal.h"
#include "protocol.h"

// Field-side ESP-NOW link. Receives commands from the gateway, reassembles
// chunked config pushes, handles timesync and emits telemetry / hello frames.
//
// Reliability model:
//  * Config is transferred as N chunks plus a commit frame carrying the whole
//    document CRC. A config is only applied and persisted after a valid
//    commit, so a partial push never takes effect.
//  * Every received command is answered with an ACK so the gateway can retry.
class FieldLink {
 public:
  using ConfigAppliedCallback = void (*)(const RuntimeConfig& config);
  using ManualOverrideCallback = void (*)(const bool values[ACT_COUNT]);
  using ActuatorCommandCallback = bool (*)(uint8_t index, bool state);
  using SeqPersistCallback = void (*)(uint16_t seq);

  void begin(ConfigAppliedCallback on_config);
  void setSeqPersistCallback(SeqPersistCallback cb) { seq_callback_ = cb; }
  void setLastCommandSeq(uint16_t seq) { last_command_seq_ = seq; }
  void setManualOverrideCallback(ManualOverrideCallback cb) { manual_callback_ = cb; }
  void setActuatorCommandCallback(ActuatorCommandCallback cb) { actuator_callback_ = cb; }

  // Reject config pushes older than the version already persisted in NVS.
  void setMinConfigVersion(uint16_t version) { min_config_version_ = version; }

  // Pin the gateway MAC instead of learning it from the first command.
  void setGatewayMac(const uint8_t mac[6]) {
    memcpy(gateway_mac_, mac, 6);
    gateway_known_ = true;
  }

  // Drain inbound ESP-NOW frames and process them.
  void poll(uint32_t now_ms);

  // Periodic outbound frames.
  void sendHello(uint32_t now_ms);
  void sendTelemetry(const TelemetryData& telemetry);
  void sendAck(uint16_t ack_seq, uint8_t command, uint16_t version, uint8_t status);

  // Sends a raw frame to the gateway. Once the gateway MAC is known (learned
  // from any command it sends us) this is a unicast send, which ESP-NOW
  // acknowledges and retransmits at the link layer. Before that it falls back
  // to broadcast so discovery still works.
  bool sendToGateway(const uint8_t* data, size_t length);
  bool gatewayKnown() const { return gateway_known_; }

  // Diagnostic event forwarded to the gateway (severity 0=info, 1=warning,
  // 2=critical). Used to surface camera status over the USB monitor.
  void sendEvent(uint8_t severity, const char* code, const char* message);

  // Time sync from the gateway (epoch seconds). Returns true when applied.
  void syncEpoch(uint32_t epoch);
  bool timeSynced() const { return time_synced_; }
  uint32_t epochNow() const;

 private:
  void handleFrame(const EspNowMessage& frame);
  void handleCommand(const CommandMsg& msg);
  void handleConfigChunk(const CommandMsg& msg);
  void handleConfigCommit(const CommandMsg& msg);
  void resetConfigAssembly();

  static void copyDeviceId(char* out, size_t out_size);

  ConfigAppliedCallback config_callback_ = nullptr;
  ManualOverrideCallback manual_callback_ = nullptr;
  ActuatorCommandCallback actuator_callback_ = nullptr;
  SeqPersistCallback seq_callback_ = nullptr;
  uint16_t min_config_version_ = 0;
  uint16_t last_command_seq_ = 0;

  // Config chunk assembly.
  uint16_t config_version_ = 0;
  uint16_t config_total_chunks_ = 0;
  uint16_t config_received_chunks_ = 0;
  size_t config_buffer_len_ = 0;
  static const size_t kConfigBufferMax = 2048;
  char config_buffer_[kConfigBufferMax];

  bool time_synced_ = false;
  uint32_t epoch_base_ = 0;
  uint32_t epoch_base_ms_ = 0;

  uint32_t last_hello_ms_ = 0;

  uint8_t gateway_mac_[6] = {0};
  bool gateway_known_ = false;
};

extern FieldLink fieldLink;
