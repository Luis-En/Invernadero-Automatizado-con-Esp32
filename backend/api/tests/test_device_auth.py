"""Device token enforcement for ingestion routes."""
from datetime import datetime


TELEMETRY = {
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "temperature": 25.0,
    "humidity": 70.0,
    "pressure": 1013.0,
    "soil_adc": [2000] * 6,
    "soil_pct": [50.0] * 6,
    "soil_ok": [True] * 6,
    "device_id": "field_primary",
    "sequence": 1,
}


async def test_telemetry_requires_device_token(client):
    resp = await client.post("/api/config/telemetry", json=TELEMETRY)
    assert resp.status_code in (401, 403)


async def test_telemetry_rejects_wrong_device_token(client):
    resp = await client.post(
        "/api/config/telemetry",
        json=TELEMETRY,
        headers={"X-Device-Token": "wrong"},
    )
    assert resp.status_code in (401, 403)


async def test_photo_chunk_requires_device_token(client):
    resp = await client.post(
        "/api/photos/chunk",
        params={"sequence": 1, "total_chunks": 1, "chunk_index": 0, "crc16": 0},
        files={"chunk_data": ("c.bin", b"x", "application/octet-stream")},
    )
    assert resp.status_code in (401, 403)


async def test_confirm_requires_device_token(client, auth_admin):
    applied = await client.post(
        "/api/config/apply",
        json={"config_json": {"irrigation": {"enabled": False}}, "crop_id": None},
        headers=auth_admin,
    )
    version = applied.json()["version"]
    resp = await client.post(f"/api/config/confirm/{version}")
    assert resp.status_code in (401, 403)


async def test_device_event_is_persisted_and_visible(client, auth_admin, device_headers):
    resp = await client.post(
        "/api/events/device",
        json={
            "severity": "critical",
            "code": "FIELD_OFFLINE",
            "message": "Field ESP32 not seen for over 5 minutes",
        },
        headers=device_headers,
    )
    assert resp.status_code == 201

    listed = await client.get("/api/events", headers=auth_admin)
    assert listed.status_code == 200
    codes = [event["code"] for event in listed.json()]
    assert "FIELD_OFFLINE" in codes
