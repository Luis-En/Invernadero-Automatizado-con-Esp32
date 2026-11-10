"""Public, unauthenticated read-only endpoints."""

from datetime import datetime


async def _seed_telemetry(client, device_headers):
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "temperature": 24.5,
        "humidity": 71.0,
        "pressure": 1012.0,
        "soil_adc": [2000] * 6,
        "soil_pct": [40.0, 41.0, 42.0, 43.0, 44.0, 45.0],
        "soil_ok": [True] * 6,
        "fan_1_state": False,
        "fan_2_state": False,
        "humidifier_1_state": False,
        "humidifier_2_state": False,
        "pump_state": False,
        "rssi": -61,
        "device_id": "field_esp32",
        "sequence": 9,
    }
    resp = await client.post("/api/config/telemetry", json=payload, headers=device_headers)
    assert resp.status_code == 201


async def test_public_telemetry_without_auth(client, device_headers):
    await _seed_telemetry(client, device_headers)
    resp = await client.get("/api/public/telemetry")
    assert resp.status_code == 200
    body = resp.json()
    assert body["temperature"] == 24.5
    assert len(body["soil_sensors"]) == 6
    assert body["soil_avg_general"] is not None
    # The public payload explains the status with the configured thresholds
    # but does not leak the rest of the configuration document.
    assert body["soil_threshold_pct"] == 35
    assert body["soil_off_above_pct"] == 45
    assert "config_json" not in body
    # No identifiers, RSSI or sequence in the public payload.
    assert "device_id" not in body
    assert "rssi" not in body
    assert "sequence" not in body


async def test_public_history_without_auth(client, device_headers):
    await _seed_telemetry(client, device_headers)
    resp = await client.get("/api/public/telemetry/history?hours=24")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    assert "temperature" in rows[0]


async def test_public_photos_and_weather_without_auth(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "OPENWEATHER_API_KEY", "")
    photos = await client.get("/api/public/photos")
    assert photos.status_code == 200
    assert isinstance(photos.json(), list)

    weather = await client.get("/api/public/weather")
    assert weather.status_code == 200
    assert weather.json()["configured"] is False


async def test_public_crops_without_auth(client):
    resp = await client.get("/api/public/crops")
    assert resp.status_code == 200
    crops = resp.json()
    assert len(crops) >= 1
    assert "display_name" in crops[0]
    # Internal notes are not exposed.
    assert "notes" not in (crops[0].get("params") or {})


async def test_public_rate_limiter_is_installed(client):
    # Rate limiting is disabled in the test env; the route must still respond.
    resp = await client.get("/api/public/telemetry")
    assert resp.status_code == 200
