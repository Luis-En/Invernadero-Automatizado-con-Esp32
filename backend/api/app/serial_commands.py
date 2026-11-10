"""Actuator commands over the serial bridge.

The API does not own the USB serial port; the ``serial_bridge`` service does.
It exposes ``POST /command`` and relays ``set_actuator`` to the gateway, which
translates it into an ESP-NOW ``CMD_SET_ACTUATOR`` and returns the field ACK.
"""
import httpx

from app.config import settings


class CommandUnavailable(Exception):
    pass


class CommandRejected(Exception):
    pass


class CommandTimeout(Exception):
    pass


def send_command(actuator: str, state: bool) -> dict:
    url = f"{settings.SERIAL_BRIDGE_URL.rstrip('/')}/command"
    payload = {"actuator": actuator, "state": state}
    try:
        response = httpx.post(
            url, json=payload, timeout=settings.SERIAL_BRIDGE_TIMEOUT_SECONDS
        )
    except httpx.TimeoutException as exc:
        raise CommandTimeout(
            "El gateway no confirmó el comando. El estado es incierto; revíselo antes de reintentar."
        ) from exc
    except httpx.HTTPError as exc:
        raise CommandUnavailable("No se pudo contactar el bridge serial") from exc

    if response.status_code == 503:
        raise CommandUnavailable(response.text or "Bridge serial no disponible")
    if response.status_code == 504:
        raise CommandTimeout(
            "El gateway no confirmó el comando. El estado es incierto; revíselo antes de reintentar."
        )
    if response.status_code == 409:
        raise CommandRejected(response.text or "El dispositivo rechazó el comando")
    if response.status_code >= 400:
        raise CommandRejected(response.text or "Comando rechazado")

    try:
        return response.json()
    except ValueError as exc:
        raise CommandUnavailable("Respuesta inválida del bridge serial") from exc
