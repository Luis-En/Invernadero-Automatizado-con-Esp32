#include "protocol.h"

uint16_t crc16_ccitt(const uint8_t* data, size_t length) {
  uint16_t crc = 0x0000;
  for (size_t i = 0; i < length; i++) {
    crc ^= (uint16_t)data[i] << 8;
    for (uint8_t bit = 0; bit < 8; bit++) {
      if (crc & 0x8000) {
        crc = (crc << 1) ^ 0x1021;
      } else {
        crc <<= 1;
      }
    }
  }
  return crc;
}

void decodeTelemetry(const TelemetryMsg& msg, int8_t linkRssi, TelemetryData& out) {
  out.epoch = msg.epoch;
  out.temperature = msg.temperature_c_x100 / 100.0f;
  out.humidity = msg.humidity_pct_x100 / 100.0f;
  out.pressure = (float)msg.pressure_hpa;

  for (uint8_t i = 0; i < SOIL_SENSOR_COUNT; i++) {
    out.soil[i].adc = msg.soil_adc[i];
    out.soil[i].pct = (float)msg.soil_pct[i];
    out.soil[i].ok = ((msg.soil_ok_mask >> i) & 0x01) != 0;
  }

  for (uint8_t i = 0; i < ACT_COUNT; i++) {
    out.actuators[i] = ((msg.actuator_mask >> i) & 0x01) != 0;
  }

  out.rssi = linkRssi != 0 ? linkRssi : msg.rssi;
  out.sequence = msg.hdr.seq;
  out.device_id[0] = '\0';
}

void decodePhotoChunk(const PhotoChunkMsg& msg, PhotoChunkData& out) {
  out.sequence = msg.sequence;
  out.total_chunks = msg.total_chunks;
  out.chunk_index = msg.chunk_index;
  out.crc16 = msg.crc16;
  out.length = msg.data_len > ESPNOW_PHOTO_DATA_MAX ? ESPNOW_PHOTO_DATA_MAX : msg.data_len;
  memcpy(out.data, msg.data, out.length);
  out.device_id[0] = '\0';
}
