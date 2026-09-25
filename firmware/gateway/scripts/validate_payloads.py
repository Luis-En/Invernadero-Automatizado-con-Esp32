"""Validates gateway payloads against the backend schema.

Reads the JSON lines produced by tools/check_payloads.cpp. Uses the backend's
ReadingBase model when pydantic is importable and falls back to a structural
check otherwise.
"""

import json
import os
import sys

TELEMETRY_KEYS = {
    "timestamp",
    "temperature",
    "humidity",
    "pressure",
    "soil_adc",
    "soil_pct",
    "soil_ok",
    "fan_1_state",
    "fan_2_state",
    "humidifier_1_state",
    "humidifier_2_state",
    "pump_state",
    "rssi",
    "device_id",
    "sequence",
}
PHOTO_KEYS = {"sequence", "total_chunks", "chunk_index", "crc16", "data", "device_id"}


def main(path: str) -> int:
    with open(path) as handle:
        lines = [line for line in handle.read().splitlines() if line.strip()]
    assert len(lines) == 2, f"expected 2 payload lines, got {len(lines)}"

    telemetry = json.loads(lines[0])
    assert telemetry.pop("type") == "telemetry"
    assert TELEMETRY_KEYS <= set(telemetry), TELEMETRY_KEYS - set(telemetry)
    assert len(telemetry["soil_adc"]) == len(telemetry["soil_pct"]) == len(telemetry["soil_ok"]) == 6

    photo = json.loads(lines[1])
    assert photo["type"] == "photo_chunk"
    assert PHOTO_KEYS <= set(photo), PHOTO_KEYS - set(photo)
    raw = bytes.fromhex(photo["data"])
    assert len(raw) == 200, len(raw)

    backend_api = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend", "api"))
    try:
        sys.path.insert(0, backend_api)
        from app.schemas import ReadingBase  # noqa: E402

        validated = ReadingBase.model_validate(telemetry)
        print(f"telemetry validates against backend ReadingBase: device_id={validated.device_id} sequence={validated.sequence}")
    except ImportError:
        print("pydantic not available, structural check passed")

    print(f"photo_chunk decodes to {len(raw)} bytes and has all API fields")
    print("PAYLOAD VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
