"""One short-lived MQTT connection per command; only an ESP ACK is success."""
import json
import threading
from uuid import uuid4

import paho.mqtt.client as mqtt

from app.config import settings


class CommandUnavailable(Exception):
    pass


class CommandRejected(Exception):
    pass


class CommandTimeout(Exception):
    pass


def send_command(actuator: str, state: bool) -> dict:
    if not settings.MQTT_ENABLED:
        raise CommandUnavailable("MQTT deshabilitado. Configure MQTT_ENABLED=true en la API.")
    command_id = str(uuid4())
    base = f"{settings.MQTT_TOPIC_PREFIX}/{settings.MQTT_DEVICE_ID}"
    command = {"command_id": command_id, "actuator": actuator, "state": state}
    done = threading.Event()
    result = {}
    errors = []
    rejected = []
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"api-{command_id}", reconnect_on_failure=False)
    client.connect_timeout = settings.MQTT_TIMEOUT_SECONDS
    if settings.MQTT_USERNAME:
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    if settings.MQTT_TLS:
        client.tls_set()

    def on_connect(c, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            errors.append("El broker rechazó la conexión MQTT")
            done.set()
        elif c.subscribe(f"{base}/ack", qos=1)[0] != mqtt.MQTT_ERR_SUCCESS:
            errors.append("No se pudo suscribir a las confirmaciones MQTT")
            done.set()

    def on_subscribe(c, userdata, mid, reason_codes, properties):
        if any(code.is_failure for code in reason_codes):
            errors.append("El broker rechazó la suscripción MQTT")
            done.set()
            return
        # Publish only after SUBACK, so a fast ESP response cannot be lost.
        info = c.publish(f"{base}/command", json.dumps(command), qos=1, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            errors.append("No se pudo publicar el comando MQTT")
            done.set()

    def on_message(c, userdata, msg):
        if msg.retain:
            return
        try:
            ack = json.loads(msg.payload)
            if (ack.get("command_id") == command_id
                    and ack.get("actuator") == actuator
                    and ack.get("status") == "rejected"):
                rejected.append(True)
                done.set()
                return
            if (ack.get("command_id") == command_id
                    and ack.get("actuator") == actuator
                    and type(ack.get("state")) is bool
                    and ack["state"] == state
                    and ack.get("status") == "applied"):
                result.update(ack)
                done.set()
        except (ValueError, AttributeError, TypeError):
            pass

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    try:
        client.connect(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=20)
        client.loop_start()
        if not done.wait(settings.MQTT_TIMEOUT_SECONDS):
            raise CommandTimeout("El ESP32 no confirmó el comando. El estado es incierto; revise el dispositivo antes de reintentar.")
        if rejected:
            raise CommandRejected("El ESP32 rechazó el comando; revise su configuración local de riego")
        if errors:
            raise CommandUnavailable(errors[0])
        return result
    except (OSError, ValueError, RuntimeError) as exc:
        raise CommandUnavailable("No se pudo conectar o enviar al broker MQTT") from exc
    finally:
        client.disconnect()
        client.loop_stop()
