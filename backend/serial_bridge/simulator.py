"""Synthetic field-node simulator and HTTP bridge.

Used when SIMULATE=true so the backend/UI can be developed without any
hardware attached. It reproduces the field firmware behaviour (hysteresis on
temperature, humidity and soil) and pushes telemetry + chunked photos to the
FastAPI backend over HTTP, mirroring what the ESP32 gateway will do over USB.

Run: `python simulator.py`
"""
import asyncio
import binascii
import logging
import os
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("simulator")

CHUNK_SIZE = 200
JPEG_HEADER = bytes.fromhex("FFD8FFE000104A46494600010100000100010000")
JPEG_FOOTER = bytes.fromhex("FFD9")


@dataclass
class SoilSensor:
    adc: int
    pct: float
    ok: bool


@dataclass
class Telemetry:
    timestamp: str
    temperature: float
    humidity: float
    pressure: float
    soil_sensors: list
    actuators: dict
    rssi: int
    device_id: str
    sequence: int


class Simulator:
    """Synthetic field node reproducing the firmware automation loop."""

    def __init__(self):
        self.sequence = 0
        self.actuators = {
            "fan_1": False,
            "fan_2": False,
            "humidifier_1": False,
            "humidifier_2": False,
            "pump": False,
        }
        self.config = self._default_config()
        self.photo_interval = int(os.getenv("SIM_PHOTO_INTERVAL_MIN", "30")) * 60
        # First photo fires FIRST_PHOTO_DELAY_SEC after boot (default 30s) so
        # the UI shows a picture quickly during development.
        first_delay = int(os.getenv("SIM_FIRST_PHOTO_DELAY_SEC", "30"))
        self.last_photo_time = time.time() - self.photo_interval + first_delay
        self.telemetry_interval = int(os.getenv("SIM_TELEMETRY_INTERVAL_SEC", "30"))
        self.photo_sequence = 0
        self.base_temp = 26.5
        self.base_humidity = 72.0
        self.base_pressure = 1013.25
        self.soil_base = [45, 42, 48, 40, 44, 38]

    def _default_config(self) -> dict:
        return {
            "version": 1,
            "crop": "tomate",
            "hysteresis": {
                "temp": {"on_above": 30.0, "off_below": 27.5},
                "humidity": {"on_below": 60.0, "off_above": 68.0},
                "soil": {"on_below_pct": 35, "off_above_pct": 45},
            },
            "irrigation": {"enabled": False},
            "safety": {
                "max_on_seconds": {"fan": 7200, "humidifier": 7200, "pump": 900}
            },
        }

    def update_config(self, config: dict):
        if isinstance(config, dict) and config:
            merged = self._default_config()
            merged.update(config)
            self.config = merged
            logger.info("Applied config v%s", config.get("version", "?"))

    def simulate_telemetry(self) -> Telemetry:
        self.sequence += 1

        self.base_temp = max(18, min(35, self.base_temp + random.uniform(-0.3, 0.3)))
        self.base_humidity = max(40, min(95, self.base_humidity + random.uniform(-1.5, 1.5)))
        self.base_pressure = max(990, min(1030, self.base_pressure + random.uniform(-0.5, 0.5)))

        soil_sensors = []
        for base in self.soil_base:
            pct = max(0.0, min(100.0, base + random.uniform(-1.0, 1.0)))
            adc = max(0, min(4095, int(4095 * (1 - pct / 100)) + random.randint(-50, 50)))
            ok = random.random() >= 0.02
            if not ok:
                pct = 0.0
            soil_sensors.append(SoilSensor(adc=adc, pct=round(pct, 1), ok=ok))

        self._apply_automation(soil_sensors)

        return Telemetry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            temperature=round(self.base_temp, 1),
            humidity=round(self.base_humidity, 1),
            pressure=round(self.base_pressure, 1),
            soil_sensors=[asdict(s) for s in soil_sensors],
            actuators=self.actuators.copy(),
            rssi=-random.randint(40, 85),
            device_id="field_esp32",
            sequence=self.sequence,
        )

    def _apply_automation(self, soil_sensors):
        hyst = self.config.get("hysteresis", {})
        irrigation_enabled = self.config.get("irrigation", {}).get("enabled", False)

        temp_hyst = hyst.get("temp", {"on_above": 30.0, "off_below": 27.5})
        hum_hyst = hyst.get("humidity", {"on_below": 60.0, "off_above": 68.0})
        soil_hyst = hyst.get("soil", {"on_below_pct": 35, "off_above_pct": 45})

        manual = self.config.get("manual_override", {})

        if self.base_temp >= temp_hyst["on_above"]:
            self.actuators["fan_1"] = self.actuators["fan_2"] = True
        elif self.base_temp <= temp_hyst["off_below"]:
            self.actuators["fan_1"] = self.actuators["fan_2"] = False

        if self.base_humidity <= hum_hyst["on_below"]:
            self.actuators["humidifier_1"] = self.actuators["humidifier_2"] = True
        elif self.base_humidity >= hum_hyst["off_above"]:
            self.actuators["humidifier_1"] = self.actuators["humidifier_2"] = False

        valid_soil = [s.pct for s in soil_sensors if s.ok]
        avg_soil = sum(valid_soil) / len(valid_soil) if valid_soil else 50

        if irrigation_enabled and avg_soil <= soil_hyst["on_below_pct"]:
            self.actuators["pump"] = True
        elif avg_soil >= soil_hyst["off_above_pct"]:
            self.actuators["pump"] = False

        for name, value in manual.items():
            if name in self.actuators and isinstance(value, bool):
                self.actuators[name] = value

    def should_send_photo(self) -> bool:
        now = time.time()
        if now - self.last_photo_time >= self.photo_interval:
            self.last_photo_time = now
            return True
        return False

    def generate_photo_chunks(self) -> list:
        self.photo_sequence += 1
        dummy_jpeg = self._generate_dummy_jpeg()
        total = (len(dummy_jpeg) + CHUNK_SIZE - 1) // CHUNK_SIZE
        chunks = []
        for index, start in enumerate(range(0, len(dummy_jpeg), CHUNK_SIZE)):
            data = dummy_jpeg[start:start + CHUNK_SIZE]
            chunks.append({
                "sequence": self.photo_sequence,
                "total_chunks": total,
                "chunk_index": index,
                "data": data.hex(),
                "crc16": binascii.crc_hqx(data, 0) & 0xFFFF,
            })
        return chunks

    @staticmethod
    def _generate_dummy_jpeg() -> bytes:
        # Keep the payload ~30 KB to mimic a VGA JPEG.
        return JPEG_HEADER + bytes(random.randint(0, 255) for _ in range(30000)) + JPEG_FOOTER
