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
from typing import Optional

import httpx

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
        self.device_username = os.getenv("DEVICE_USERNAME", "viewer")
        self.device_password = os.getenv("DEVICE_PASSWORD", "viewer123")
        self._token: Optional[str] = None

    async def _ensure_token(self) -> None:
        if self._token:
            return
        try:
            resp = await self.client.post(
                f"{self.api_url}/api/auth/login",
                json={"username": self.device_username, "password": self.device_password},
            )
            if resp.status_code == 200:
                self._token = resp.json().get("access_token")
            else:
                logger.warning("device login failed: %s", resp.status_code)
        except Exception as exc:
            logger.debug("device login error: %s", exc)

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

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
        await self._ensure_token()
        response = await self.client.get(
            f"{self.api_url}/api/config/active", headers=self._auth_headers()
        )
        if response.status_code == 401:
            self._token = None
            return
        if response.status_code == 200:
            config = response.json()
            self.simulator.update_config(config.get("config_json", {}))
            version = config.get("version")
            if version is not None:
                try:
                    await self.client.post(
                        f"{self.api_url}/api/config/confirm/{version}",
                        headers=self._auth_headers(),
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

        async for message in self.source.messages():
            await self._dispatch(message)

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
            await self._post_telemetry(message)
        elif kind == "photo_chunk":
            await self._post_photo_chunk(message)
        elif kind == "hello":
            logger.info("gateway online: %s firmware=%s", message.get("device_id"), message.get("firmware"))
            if self.source is not None:
                self.source.write_json({"type": "timesync", "epoch": int(time.time())})
        elif kind == "event":
            logger.warning("gateway event %s: %s", message.get("code"), message.get("message"))
        elif kind == "device_status":
            logger.info(
                "gateway status: field=%s camera=%s field_rssi=%s",
                message.get("field_online"),
                message.get("camera_online"),
                message.get("field_rssi"),
            )
        elif kind == "config_ack":
            logger.info("gateway config ack v%s: %s", message.get("version"), message.get("status"))
        else:
            logger.debug("ignoring gateway message type=%s", kind)

    # ------------------------------------------------------------------
    # API posting
    # ------------------------------------------------------------------

    async def _post_telemetry(self, message: dict) -> None:
        payload = {key: value for key, value in message.items() if key != "type"}
        try:
            await self.client.post(f"{self.api_url}{TELEMETRY_URL}", json=payload)
        except Exception as exc:
            logger.warning("failed to post telemetry: %s", exc)

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
                f"{self.api_url}{PHOTO_CHUNK_URL}", params=params, files=files
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
