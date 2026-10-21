# Control de actuadores por MQTT

Al pulsar **Encender/Apagar** como administrador:

1. React llama a `POST /api/actuators/{actuador}/command` con `{"state": true}` o `false`.
2. La API se suscribe a las confirmaciones y publica inmediatamente el comando MQTT.
3. El ESP32 aplica la salida y publica un ACK con el mismo `command_id`.
4. La API devuelve el ACK y el dashboard cambia el botón. La telemetría posterior vuelve a ser la fuente del estado.

No se espera el sondeo de configuración del puente serial. El broker y el ESP deben estar conectados para completar la operación. El ACK confirma que el firmware aplicó el GPIO; no confirma físicamente que un relé o motor haya funcionado.

## 1. Broker y aplicación con Docker

Desde la raíz del proyecto:

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.mqtt.yml up -d --build
```

Este comando añade Mosquitto en el puerto TCP 1883. La API usa `mqtt:1883` dentro de Docker. El ESP usa la **IP LAN** del equipo donde corre Docker, por ejemplo `192.168.1.100`, nunca `localhost` ni `mqtt`.

El broker de ejemplo permite conexiones anónimas para pruebas dentro de una red de confianza. Para acceso remoto, configure autenticación, ACL por dispositivo y TLS; no publique el puerto anónimo a Internet. La API admite `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_TLS`. El firmware de ejemplo usa TCP sin TLS y admite usuario/contraseña; TLS en ESP requiere sustituir WiFiClient por WiFiClientSecure y configurar un certificado de confianza.

## 2. Preparar el ESP32 de campo existente

No hace falta reemplazar el firmware por otro sketch. El receptor MQTT se integra en `firmware/field` y conserva sensores, actuadores, cámara y ESP-NOW.

```bash
cp firmware/field/include/mqtt_config.example.h firmware/field/include/mqtt_config.h
```

Edite `mqtt_config.h`: SSID, contraseña y `FIELD_MQTT_HOST` (IP LAN del broker). Si activó autenticación, complete usuario/contraseña. Este archivo queda excluido de Git.

**Radio compartida:** el router Wi-Fi de 2.4 GHz debe usar canal fijo **6**, el mismo del gateway ESP-NOW y del AP de la cámara. Un canal distinto puede interrumpir ESP-NOW. El ESP mantiene AP+STA para recibir fotos y conectar al broker.

Compile y cargue con PlatformIO:

```bash
cd firmware/field
pio run -e field -t upload
pio device monitor
```

Para pruebas sin sensores existe `field_bench`. Busque en el monitor `[mqtt] subscribed invernadero/field_esp32/command`. Sin `mqtt_config.h`, MQTT permanece deshabilitado en el firmware.

## 3. Telemetría real y simulador

El MQTT añadido transporta comandos y confirmaciones. La telemetría, las fotos y la configuración de cultivo siguen usando el gateway y el puente serial existentes.

Para usar el invernadero real, evite que el simulador publique estados ficticios que sobrescriban los estados de la pantalla. Configure `SIMULATE=false` en `.env` y use la configuración serial real del proyecto (`docker-compose.serial.yml`, dispositivo USB correcto). Consulte su guía serial y hardware existente.

Si solo prueba comandos sin gateway, puede detener el simulador:

```bash
docker compose stop serial-bridge
```

En esa prueba los estados confirmados se muestran en la sesión actual del dashboard, pero no hay nueva telemetría de sensores ni persistencia de esos estados al recargar. Para monitoreo continuo mantenga el gateway real conectado.

## 4. API ejecutada sin Docker

Instale `backend/api/requirements.txt` y defina las variables MQTT en el entorno de la API (o en su `.env` del directorio desde el que la inicia):

```dotenv
MQTT_ENABLED=true
MQTT_HOST=192.168.1.100
MQTT_PORT=1883
MQTT_DEVICE_ID=field_esp32
MQTT_TOPIC_PREFIX=invernadero
MQTT_TIMEOUT_SECONDS=5
```

Con Docker, `docker-compose.mqtt.yml` activa MQTT y fija host/puerto/dispositivo/prefijo. Si cambia esos valores, edite también el override y mantenga la misma identidad y prefijo en el firmware. Los secretos y TLS para Docker deben añadirse al bloque `api.environment`.

## Protocolo

Topic de comandos: `invernadero/field_esp32/command`

```json
{"command_id":"550e8400-e29b-41d4-a716-446655440000","actuator":"fan_1","state":true}
```

Topic de respuestas: `invernadero/field_esp32/ack`

```json
{"command_id":"550e8400-e29b-41d4-a716-446655440000","actuator":"fan_1","state":true,"status":"applied"}
```

Actuadores: `fan_1`, `fan_2`, `humidifier_1`, `humidifier_2`, `pump`.
Los comandos llevan estado absoluto, QoS 1 y `retain=false`; las respuestas del ESP son QoS 0 y no retenidas. Una respuesta perdida puede producir un timeout aunque la salida haya cambiado. La API no reintenta automáticamente. No publique comandos retenidos en este topic.

El control manual MQTT afecta únicamente al actuador seleccionado y se mantiene hasta otro comando, un reinicio o una nueva configuración recibida en el ESP. Los demás actuadores siguen su automatización. Se mantienen los tiempos máximos de encendido para las salidas controladas por MQTT; al vencer, la salida queda apagada hasta otro comando. El control manual permite pruebas de ventiladores y humidificadores sin sensores.

La bomba solo se enciende si el riego está habilitado **en la API y en la configuración local del ESP**. Aplique primero la configuración de cultivo y espere la confirmación por el gateway. Apagar sigue disponible aunque se deshabilite el riego.

Errores: 403 sin rol administrador, 422 entrada inválida, 409 riego bloqueado/comando rechazado, 503 MQTT deshabilitado o broker inaccesible, 504 sin confirmación. Tras un timeout el estado es incierto; revise telemetría o el equipo antes de reintentar.

## Verificación

```bash
cd backend/api
pytest
```

También hay pruebas aisladas del transporte que no requieren dependencias instaladas ni broker:

```bash
python backend/api/tools/test_mqtt_transport.py
```

Las pruebas aisladas usan un cliente MQTT simulado; no sustituyen la compilación PlatformIO ni una prueba con el ESP32 y los relés reales.
