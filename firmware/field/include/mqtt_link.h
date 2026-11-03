#pragma once
#include <Arduino.h>
using MqttCommandHandler = bool (*)(uint8_t index, bool state);
void mqttBegin(MqttCommandHandler handler);
void mqttPoll(uint32_t now);
