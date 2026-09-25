#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>

// Wire protocol shared by field, gateway and camera nodes over ESP-NOW.
// The gateway decodes these frames and re-emits them as JSON lines over USB
// serial, so the Raspberry Pi never has to parse the binary form.
//
// Serial line contract (both directions):
//   <json>*<CRC16 hex>\n
// CRC16 is CRC-16/CCITT-FALSE (poly 0x1021, init 0x0000), the same value
// Python computes with binascii.crc_hqx(data, 0).

static const uint8_t ESPNOW_MAGIC = 0x67;  // 'g'
static const uint8_t ESPNOW_PROTO_VERSION = 1;
static const uint8_t ESPNOW_BROADCAST_MAC[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

enum EspNowMsgType : uint8_t {
  MSG_TELEMETRY = 0x01,
  MSG_PHOTO_CHUNK = 0x02,
  MSG_COMMAND = 0x03,
  MSG_ACK = 0x04,
  MSG_HELLO = 0x05,
  // Short human-readable diagnostic from a node (e.g. the field node reporting
  // a camera connect/upload failure). The gateway forwards it to the serial
  // bridge as an "event" line.
  MSG_EVENT = 0x06,
};

enum DeviceRole : uint8_t {
  ROLE_UNKNOWN = 0,
  ROLE_FIELD = 1,
  ROLE_GATEWAY = 2,
  ROLE_CAMERA = 3,
};

enum CommandCode : uint8_t {
  CMD_SET_CONFIG_CHUNK = 1,
  CMD_SET_CONFIG_COMMIT = 2,
  CMD_TIMESYNC = 3,
  CMD_REBOOT = 4,
  CMD_PURGE = 5,
  CMD_PING = 6,
};

enum ActuatorIndex : uint8_t {
  ACT_FAN_1 = 0,
  ACT_FAN_2 = 1,
  ACT_HUMIDIFIER_1 = 2,
  ACT_HUMIDIFIER_2 = 3,
  ACT_PUMP = 4,
  ACT_COUNT = 5,
};

static const uint8_t SOIL_SENSOR_COUNT = 6;
static const size_t ESPNOW_MAX_FRAME = 250;
static const size_t ESPNOW_PHOTO_DATA_MAX = 200;
static const size_t ESPNOW_CMD_PAYLOAD_MAX = 160;

struct __attribute__((packed)) EspNowHeader {
  uint8_t magic;
  uint8_t version;
  uint8_t type;
  uint8_t src[6];
  uint16_t seq;
};

struct __attribute__((packed)) TelemetryMsg {
  EspNowHeader hdr;
  uint32_t epoch;
  int16_t temperature_c_x100;
  uint16_t humidity_pct_x100;
  uint16_t pressure_hpa;
  uint16_t soil_adc[SOIL_SENSOR_COUNT];
  uint8_t soil_pct[SOIL_SENSOR_COUNT];
  uint8_t soil_ok_mask;
  uint8_t actuator_mask;
  int8_t rssi;
};

struct __attribute__((packed)) PhotoChunkMsg {
  EspNowHeader hdr;
  uint16_t sequence;
  uint16_t total_chunks;
  uint16_t chunk_index;
  uint16_t crc16;
  uint16_t data_len;
  uint8_t data[ESPNOW_PHOTO_DATA_MAX];
};

struct __attribute__((packed)) CommandMsg {
  EspNowHeader hdr;
  uint8_t cmd;
  uint8_t flags;
  uint16_t version;
  uint16_t index;
  uint16_t total;
  uint32_t arg;
  uint16_t payload_len;
  uint8_t payload[ESPNOW_CMD_PAYLOAD_MAX];
};

struct __attribute__((packed)) AckMsg {
  EspNowHeader hdr;
  uint16_t ack_seq;
  uint16_t version;
  uint8_t cmd;
  uint8_t status;
};

struct __attribute__((packed)) HelloMsg {
  EspNowHeader hdr;
  uint8_t role;
  uint8_t fw_major;
  uint8_t fw_minor;
  uint8_t fw_patch;
  uint32_t uptime_s;
  char device_id[16];
};

// Diagnostic event. `severity` mirrors the backend event levels and `code` is a
// short machine-friendly tag (e.g. "CAM_AP_UP", "PHOTO_OK", "PHOTO_FAIL").
struct __attribute__((packed)) EventMsg {
  EspNowHeader hdr;
  uint8_t severity;  // 0=info, 1=warning, 2=critical
  uint8_t role;
  char code[24];
  char message[64];
};

static_assert(sizeof(EspNowHeader) == 11, "EspNowHeader must be 11 bytes");
static_assert(sizeof(TelemetryMsg) == 42, "TelemetryMsg must be 42 bytes");
static_assert(sizeof(PhotoChunkMsg) == 221, "PhotoChunkMsg must be 221 bytes");
static_assert(sizeof(CommandMsg) == 185, "CommandMsg must be 185 bytes");
static_assert(sizeof(AckMsg) == 17, "AckMsg must be 17 bytes");
static_assert(sizeof(HelloMsg) == 35, "HelloMsg must be 35 bytes");
static_assert(sizeof(EventMsg) == 101, "EventMsg must be 101 bytes");
static_assert(sizeof(TelemetryMsg) <= ESPNOW_MAX_FRAME, "Telemetry exceeds ESP-NOW limit");
static_assert(sizeof(CommandMsg) <= ESPNOW_MAX_FRAME, "Command exceeds ESP-NOW limit");
static_assert(sizeof(EventMsg) <= ESPNOW_MAX_FRAME, "Event exceeds ESP-NOW limit");

struct SoilSample {
  uint16_t adc;
  float pct;
  bool ok;
};

struct TelemetryData {
  uint32_t epoch;
  float temperature;
  float humidity;
  float pressure;
  SoilSample soil[SOIL_SENSOR_COUNT];
  bool actuators[ACT_COUNT];
  int8_t rssi;
  char device_id[24];
  uint16_t sequence;
};

struct PhotoChunkData {
  uint16_t sequence;
  uint16_t total_chunks;
  uint16_t chunk_index;
  uint16_t crc16;
  uint16_t length;
  uint8_t data[ESPNOW_PHOTO_DATA_MAX];
  char device_id[24];
};

struct DeviceStatus {
  bool field_online;
  bool camera_online;
  int8_t field_rssi;
  int8_t camera_rssi;
  uint32_t field_last_seen_s;
  uint32_t camera_last_seen_s;
  uint16_t config_version;
  uint32_t uptime_s;
  uint32_t free_heap;
  bool simulate;
};

uint16_t crc16_ccitt(const uint8_t* data, size_t length);

void decodeTelemetry(const TelemetryMsg& msg, int8_t linkRssi, TelemetryData& out);
void decodePhotoChunk(const PhotoChunkMsg& msg, PhotoChunkData& out);
