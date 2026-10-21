#pragma once
// Copy to mqtt_config.h and replace these values. Do not commit passwords.
#define FIELD_MQTT_ENABLED 1
#define FIELD_MQTT_WIFI_SSID "TU_WIFI"
#define FIELD_MQTT_WIFI_PASSWORD "TU_CLAVE_WIFI"
// LAN IP of the PC/Raspberry Pi running Mosquitto; never localhost or mqtt.
#define FIELD_MQTT_HOST "192.168.1.100"
#define FIELD_MQTT_PORT 1883
#define FIELD_MQTT_USER ""
#define FIELD_MQTT_PASSWORD ""
#define FIELD_MQTT_PREFIX "invernadero"
