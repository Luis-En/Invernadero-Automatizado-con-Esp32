#include "mqtt_link.h"
#include "config.h"
#if __has_include("mqtt_config.h")
#include "mqtt_config.h"
#endif
#ifndef FIELD_MQTT_ENABLED
#define FIELD_MQTT_ENABLED 0
#endif

#if FIELD_MQTT_ENABLED
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
namespace {
WiFiClient transport;
PubSubClient client(transport);
MqttCommandHandler commandHandler = nullptr;
String base;
uint32_t lastAttempt = 0;
const char* names[] = {"fan_1", "fan_2", "humidifier_1", "humidifier_2", "pump"};

void receiveCommand(char* topic, byte* payload, unsigned int length) {
  if (String(topic) != base + "/command") return;
  StaticJsonDocument<384> doc;
  if (deserializeJson(doc, payload, length)) return;
  if (!doc["command_id"].is<const char*>() ||
      !doc["actuator"].is<const char*>() || !doc["state"].is<bool>()) return;
  const String id = doc["command_id"].as<String>();
  if (id.length() != 36) return;
  const String actuator = doc["actuator"].as<String>();
  const bool state = doc["state"].as<bool>();
  for (uint8_t i = 0; i < 5; ++i) {
    if (actuator != names[i]) continue;
    const bool applied = commandHandler && commandHandler(i, state);
    // Own copies are needed: PubSubClient reuses its receive buffer to publish.
    doc.clear();
    doc["command_id"] = id;
    doc["actuator"] = actuator;
    doc["state"] = state;
    doc["status"] = applied ? "applied" : "rejected";
    char ack[256];
    serializeJson(doc, ack, sizeof(ack));
    client.publish((base + "/ack").c_str(), ack, false);
    Serial.printf("[mqtt] %s=%d %s\n", actuator.c_str(), state, applied ? "applied" : "rejected");
    return;
  }
}
}

void mqttBegin(MqttCommandHandler handler) {
  commandHandler = handler;
  base = String(FIELD_MQTT_PREFIX) + "/" + FIELD_DEVICE_ID;
  WiFi.mode(WIFI_AP_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(FIELD_MQTT_WIFI_SSID, FIELD_MQTT_WIFI_PASSWORD);
  transport.setConnectionTimeout(1000);
  client.setServer(FIELD_MQTT_HOST, FIELD_MQTT_PORT);
  client.setCallback(receiveCommand);
  client.setBufferSize(512);
  client.setSocketTimeout(1);
  Serial.println("[mqtt] Wi-Fi connecting (AP/gateway/router must share channel 6)");
}

void mqttPoll(uint32_t now) {
  if (WiFi.status() != WL_CONNECTED) return;
  if (client.connected()) {
    client.loop();
    return;
  }
  if (now - lastAttempt < 3000) return;
  lastAttempt = now;
  const String clientId = String(FIELD_DEVICE_ID) + "-" + WiFi.macAddress();
  if (client.connect(clientId.c_str(), FIELD_MQTT_USER, FIELD_MQTT_PASSWORD)) {
    if (!client.subscribe((base + "/command").c_str(), 1)) client.disconnect();
    else Serial.printf("[mqtt] subscribed %s/command\n", base.c_str());
  }
}
#else
void mqttBegin(MqttCommandHandler) {}
void mqttPoll(uint32_t) {}
#endif
