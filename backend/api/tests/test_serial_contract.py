"""Integration: gateway serial line -> bridge parser -> API telemetry."""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path


def _load_gateway_protocol():
    path = (
        Path(__file__).resolve().parents[2]
        / "serial_bridge"
        / "gateway_protocol.py"
    )
    spec = importlib.util.spec_from_file_location("gateway_protocol", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


gateway_protocol = _load_gateway_protocol()


def _telemetry_message():
    return {
        "type": "telemetry",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "temperature": 26.4,
        "humidity": 71.0,
        "pressure": 1012.8,
        "soil_adc": [2000, 2100, 1900, 2200, 2300, 2050],
        "soil_pct": [50.0, 48.0, 53.0, 45.0, 43.0, 48.0],
        "soil_ok": [True] * 6,
        "fan_1_state": False,
        "fan_2_state": False,
        "humidifier_1_state": False,
        "humidifier_2_state": False,
        "pump_state": False,
        "rssi": -70,
        "device_id": "field_primary",
        "sequence": 7,
    }


async def test_serial_frame_roundtrip_and_ingest(client, device_headers, auth_admin):
    framed = gateway_protocol.frame_line(_telemetry_message())
    parsed = gateway_protocol.parse_line(framed)

    assert parsed is not None
    assert parsed["temperature"] == 26.4

    payload = {key: value for key, value in parsed.items() if key != "type"}
    ingest = await client.post(
        "/api/config/telemetry", json=payload, headers=device_headers
    )
    assert ingest.status_code == 201, ingest.text

    latest = await client.get(
        "/api/config/telemetry/latest", headers=auth_admin
    )
    assert latest.status_code == 200
    assert latest.json()["temperature"] == 26.4
    assert latest.json()["sequence"] == 7


def test_corrupted_serial_line_is_dropped():
    framed = gateway_protocol.frame_line(_telemetry_message())
    corrupted = framed.replace(b"26.4", b"99.9")
    assert gateway_protocol.parse_line(corrupted) is None
