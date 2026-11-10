"""Serial bridge for the greenhouse system.

Two sources feed the FastAPI backend:

* SIMULATE=true (default): a synthetic field node, for development without
  hardware.
* SIMULATE=false: the ESP32 gateway over USB serial. The bridge parses the
  gateway's JSON lines, verifies their CRC16 and forwards ``telemetry`` and
  ``photo_chunk`` messages to the API.
"""

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from aiohttp import web

from serial_source import SerialSource
from simulator import Simulator

logger = logging.getLogger(__name__)

TELEMETRY_URL = "/api/config/telemetry"
PHOTO_CHUNK_URL = "/api/photos/chunk"


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class SerialBridge:
    def __init__(self) -> None:
        self.api_url = os.getenv("API_URL", "http://localhost:8000")
        self.client = httpx.AsyncClient(timeout=10.0)
        self.running = False
        self.simulate = _env_flag("SIMULATE", True)
        self.serial_port = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
        self.baudrate = int(os.getenv("SERIAL_BAUDRATE", "115200"))
        self.simulator = Simulator()
        self.source: Optional[SerialSource] = None
        # Shared device token. Empty means the API rejects device writes, which
        # is the intended fail-closed default.
        self.device_token = os.getenv("DEVICE_API_TOKEN", "").strip()
        # Latest frame from each field node. The two nodes are merged into a
        # single 6-slot reading so the backend/frontend keep their current model
        # (slots 0-1 = primary probes 34/35, slots 2-5 = secondary probes 32-35).
        self.primary: Optional[dict] = None
        self.secondary: Optional[dict] = None
        # command_id -> Future resolved by the gateway's serial actuator_ack.
        self.pending_commands: dict[str, asyncio.Future] = {}
        self.http_port = int(os.getenv("BRIDGE_HTTP_PORT", "8081"))

    def _device_headers(self) -> dict:
        # The API enforces HTTPS in production. This bridge is an internal,
        # trusted client (it talks to the API over the Compose network), so it
        # declares the secure scheme the same way the TLS proxy does.
        headers = {"X-Forwarded-Proto": "https"}
        if self.device_token:
            headers["X-Device-Token"] = self.device_token
        return headers

    async def start(self) -> None:
        self.running = True
        if self.simulate:
            logger.info("serial bridge starting in simulation mode")
            await self._run_simulation()
        else:
            logger.info("serial bridge starting in serial mode on %s", self.serial_port)
            await self._run_serial()

    async def stop(self) -> None:
        self.running = False
        await self.client.aclose()

    # ------------------------------------------------------------------
    # Simulation source
    # ------------------------------------------------------------------

    async def _run_simulation(self) -> None:
        tasks = [
            asyncio.create_task(self._telemetry_loop()),
            asyncio.create_task(self._photo_loop()),
            asyncio.create_task(self._config_poll_loop()),
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _telemetry_loop(self) -> None:
        while self.running:
            try:
                telemetry = self.simulator.simulate_telemetry()
                await self._post_telemetry(self._simulated_payload(telemetry))
                await asyncio.sleep(self.simulator.telemetry_interval)
            except Exception as exc:
                logger.error("telemetry loop error: %s", exc)
                await asyncio.sleep(5)

    async def _photo_loop(self) -> None:
        while self.running:
            try:
                if self.simulator.should_send_photo():
                    for chunk in self.simulator.generate_photo_chunks():
                        await self._post_photo_chunk({**chunk, "device_id": "camera"})
                        await asyncio.sleep(0.05)
                    logger.info("photo sequence %s uploaded", self.simulator.photo_sequence)
                await asyncio.sleep(5)
            except Exception as exc:
                logger.error("photo loop error: %s", exc)
                await asyncio.sleep(5)

    async def _config_poll_loop(self) -> None:
        while self.running:
            try:
                await self._fetch_and_apply_config()
                await asyncio.sleep(60)
            except Exception as exc:
                logger.debug("config poll failed: %s", exc)
                await asyncio.sleep(30)

    async def _fetch_and_apply_config(self) -> None:
        response = await self.client.get(
            f"{self.api_url}/api/config/device/active", headers=self._device_headers()
        )
        if response.status_code in (401, 503):
            logger.warning("device config read rejected: %s", response.status_code)
            return
        if response.status_code == 200:
            config = response.json()
            self.simulator.update_config(config.get("config_json", {}))
            version = config.get("version")
            if version is not None:
                try:
                    await self.client.post(
                        f"{self.api_url}/api/config/confirm/{version}",
                        headers=self._device_headers(),
                    )
                except Exception as exc:
                    logger.debug("config confirm failed: %s", exc)

    @staticmethod
    def _simulated_payload(telemetry) -> dict:
        return {
            "timestamp": telemetry.timestamp,
            "temperature": telemetry.temperature,
            "humidity": telemetry.humidity,
            "pressure": telemetry.pressure,
            "soil_adc": [sensor["adc"] for sensor in telemetry.soil_sensors],
            "soil_pct": [sensor["pct"] for sensor in telemetry.soil_sensors],
            "soil_ok": [sensor["ok"] for sensor in telemetry.soil_sensors],
            "fan_1_state": telemetry.actuators["fan_1"],
            "fan_2_state": telemetry.actuators["fan_2"],
            "humidifier_1_state": telemetry.actuators["humidifier_1"],
            "humidifier_2_state": telemetry.actuators["humidifier_2"],
            "pump_state": telemetry.actuators["pump"],
            "rssi": telemetry.rssi,
            "device_id": telemetry.device_id,
            "sequence": telemetry.sequence,
        }

    # ------------------------------------------------------------------
    # Serial source
    # ------------------------------------------------------------------

    async def _run_serial(self) -> None:
        self.source = SerialSource(self.serial_port, self.baudrate)
        await self.source.start()
        asyncio.create_task(self._handshake_loop())
        asyncio.create_task(self._timesync_loop())
        asyncio.create_task(self._start_http_server())

        async for message in self.source.messages():
            await self._dispatch(message)

    async def _start_http_server(self) -> None:
        app = web.Application()
        app.router.add_post("/command", self._handle_command_http)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.http_port)
        await site.start()
        logger.info("bridge command server listening on :%d", self.http_port)

    async def _handle_command_http(self, request: web.Request) -> web.Response:
        """Accept an actuator command from the API and relay it over serial.

        The gateway answers with an `actuator_ack` line carrying the same
        command_id, which resolves the future below. The API receives the real
        device confirmation, not just an HTTP 200.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"detail": "invalid JSON"}, status=400)

        actuator = body.get("actuator")
        state = body.get("state")
        if not isinstance(actuator, str) or not isinstance(state, bool):
            return web.json_response({"detail": "actuator and state are required"}, status=400)

        if self.simulate or self.source is None:
            return web.json_response(
                {"actuator": actuator, "state": state, "status": "applied"}
            )

        command_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self.pending_commands[command_id] = future

        sent = self.source.write_json(
            {
                "type": "set_actuator",
                "command_id": command_id,
                "actuator": actuator,
                "state": state,
            }
        )
        if not sent:
            self.pending_commands.pop(command_id, None)
            return web.json_response({"detail": "serial link unavailable"}, status=503)

        try:
            result = await asyncio.wait_for(future, timeout=8.0)
        except asyncio.TimeoutError:
            return web.json_response({"detail": "device did not confirm"}, status=504)
        finally:
            self.pending_commands.pop(command_id, None)

        http_status = 200 if result.get("status") == "applied" else 409
        return web.json_response(result, status=http_status)

    async def _timesync_loop(self) -> None:
        # Keep resending the clock. The gateway forwards each timesync to both
        # field nodes, and a node learns the gateway MAC from that frame, so a
        # node that boots after the first handshake still switches to unicast.
        while self.running and self.source is not None:
            if await self.source.wait_open(timeout=1.0):
                self.source.write_json({"type": "timesync", "epoch": int(time.time())})
            await asyncio.sleep(30)

    async def _handshake_loop(self) -> None:
        # Ping until the gateway answers with a hello, which triggers a
        # timesync reply in _dispatch. Handles the gateway being plugged in
        # after the bridge started.
        while self.running and self.source is not None:
            if await self.source.wait_open(timeout=5.0):
                self.source.write_json({"type": "ping"})
                return
            await asyncio.sleep(1)

    async def _dispatch(self, message: dict) -> None:
        kind = message.get("type")
        if kind == "telemetry":
            await self._handle_field_telemetry(message)
        elif kind == "photo_chunk":
            await self._post_photo_chunk(message)
        elif kind == "hello":
            logger.info("gateway online: %s firmware=%s", message.get("device_id"), message.get("firmware"))
            if self.source is not None:
                self.source.write_json({"type": "timesync", "epoch": int(time.time())})
        elif kind == "event":
            logger.warning("gateway event %s: %s", message.get("code"), message.get("message"))
            await self._post_event(message)
        elif kind == "device_status":
            logger.info(
                "gateway status: field=%s camera=%s field_rssi=%s",
                message.get("field_online"),
                message.get("camera_online"),
                message.get("field_rssi"),
            )
        elif kind == "config_ack":
            logger.info("gateway config ack v%s: %s", message.get("version"), message.get("status"))
        elif kind == "actuator_ack":
            command_id = message.get("command_id")
            future = self.pending_commands.get(command_id)
            if future is not None and not future.done():
                future.set_result(message)
            logger.info(
                "actuator %s -> %s (%s)",
                message.get("actuator"),
                message.get("state"),
                message.get("status"),
            )
        else:
            logger.debug("ignoring gateway message type=%s", kind)

    async def _handle_field_telemetry(self, message: dict) -> None:
        """Merge the two field nodes into one reading.

        The primary owns the BME280, the actuators and two probes (GPIO34/35).
        The secondary owns four probes (GPIO32-35). Posting a merged payload
        keeps the backend's 6-slot soil model and the dashboard unchanged.
        """
        if message.get("device_id") == "field_secondary":
            self.secondary = message
            # Before the primary has ever reported, still publish something.
            if self.primary is None:
                await self._post_telemetry(self._merge_fields())
            return

        self.primary = message
        await self._post_telemetry(self._merge_fields())

    @staticmethod
    def _array(source: dict, key: str, default, size: int = 6) -> list:
        value = source.get(key)
        if not isinstance(value, list) or len(value) < size:
            return [default] * size
        return value

    def _merge_fields(self) -> dict:
        primary = self.primary or {}
        secondary = self.secondary or {}

        p_adc = self._array(primary, "soil_adc", 0)
        p_pct = self._array(primary, "soil_pct", 0.0)
        p_ok = self._array(primary, "soil_ok", False)
        s_adc = self._array(secondary, "soil_adc", 0)
        s_pct = self._array(secondary, "soil_pct", 0.0)
        s_ok = self._array(secondary, "soil_ok", False)

        return {
            "timestamp": primary.get("timestamp") or secondary.get("timestamp"),
            "temperature": primary.get("temperature"),
            "humidity": primary.get("humidity"),
            "pressure": primary.get("pressure"),
            "soil_adc": [p_adc[0], p_adc[1], s_adc[0], s_adc[1], s_adc[2], s_adc[3]],
            "soil_pct": [p_pct[0], p_pct[1], s_pct[0], s_pct[1], s_pct[2], s_pct[3]],
            "soil_ok": [p_ok[0], p_ok[1], s_ok[0], s_ok[1], s_ok[2], s_ok[3]],
            "fan_1_state": primary.get("fan_1_state", False),
            "fan_2_state": primary.get("fan_2_state", False),
            "humidifier_1_state": primary.get("humidifier_1_state", False),
            "humidifier_2_state": primary.get("humidifier_2_state", False),
            "pump_state": primary.get("pump_state", False),
            "rssi": primary.get("rssi"),
            "device_id": "field_primary",
            "sequence": primary.get("sequence"),
        }

    # ------------------------------------------------------------------
    # API posting
    # ------------------------------------------------------------------

    async def _post_telemetry(self, message: dict) -> None:
        payload = {key: value for key, value in message.items() if key != "type"}
        # The field node only knows wall time once it has been time-synced.
        # Before that the gateway emits a 1970 sentinel (or no timestamp), so
        # stamp the arrival time here instead of letting the API reject an
        # absurd clock.
        timestamp = payload.get("timestamp")
        if not timestamp or str(timestamp).startswith("1970-01-01"):
            payload["timestamp"] = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
        try:
            resp = await self.client.post(
                f"{self.api_url}{TELEMETRY_URL}",
                json=payload,
                headers=self._device_headers(),
            )
            if resp.status_code >= 400:
                logger.warning("telemetry rejected: %s %s", resp.status_code, resp.text[:160])
        except Exception as exc:
            logger.warning("failed to post telemetry: %s", exc)

    async def _post_event(self, message: dict) -> None:
        severity = message.get("severity", "info")
        if severity not in ("info", "warning", "critical"):
            severity = "info"
        payload = {
            "severity": severity,
            "code": str(message.get("code", "DEVICE_EVENT"))[:50],
            "message": str(message.get("message", ""))[:2000],
            "details": {"source": "gateway"},
        }
        try:
            resp = await self.client.post(
                f"{self.api_url}/api/events/device",
                json=payload,
                headers=self._device_headers(),
            )
            if resp.status_code >= 400:
                logger.warning("event rejected: %s %s", resp.status_code, resp.text[:160])
        except Exception as exc:
            logger.warning("failed to persist event: %s", exc)

    async def _post_photo_chunk(self, chunk: dict) -> None:
        try:
            raw = bytes.fromhex(chunk["data"])
        except (KeyError, ValueError) as exc:
            logger.warning("invalid photo chunk: %s", exc)
            return

        files = {"chunk_data": ("chunk.bin", raw, "application/octet-stream")}
        params = {
            "sequence": chunk["sequence"],
            "total_chunks": chunk["total_chunks"],
            "chunk_index": chunk["chunk_index"],
            "crc16": chunk["crc16"],
            "device_id": chunk.get("device_id", "camera"),
        }
        try:
            resp = await self.client.post(
                f"{self.api_url}{PHOTO_CHUNK_URL}",
                params=params,
                files=files,
                headers=self._device_headers(),
            )
            if resp.status_code >= 400:
                logger.warning("photo chunk rejected: %s %s", resp.status_code, resp.text[:160])
        except Exception as exc:
            logger.warning("failed to post photo chunk: %s", exc)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    bridge = SerialBridge()
    try:
        await bridge.start()
    except KeyboardInterrupt:
        pass
    finally:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
