"""Config apply/confirm and telemetry ingestion tests."""
from datetime import datetime


async def _apply_config(client, headers, version_crop_name="tomate"):
    return await client.post(
        "/api/config/apply",
        json={
            "config_json": {
                "crop": version_crop_name,
                "hysteresis": {
                    "temp": {"on_above": 28.0, "off_below": 25.0},
                    "humidity": {"on_below": 65.0, "off_above": 75.0},
                    "soil": {"on_below_pct": 40, "off_above_pct": 50},
                },
                "irrigation": {"enabled": False},
                "safety": {"max_on_seconds": {"pump": 900}},
            },
            "crop_id": None,
        },
        headers=headers,
    )


async def test_apply_config_requires_admin(client, auth_viewer):
    resp = await _apply_config(client, auth_viewer)
    assert resp.status_code == 403


async def test_apply_and_confirm_config(client, auth_admin):
    applied = await _apply_config(client, auth_admin)
    assert applied.status_code == 200
    version = applied.json()["version"]

    active = await client.get("/api/config/active", headers=auth_admin)
    assert active.status_code == 200
    assert active.json()["config_json"]["hysteresis"]["temp"]["on_above"] == 28.0

    confirmed = await client.post(f"/api/config/confirm/{version}")
    assert confirmed.status_code == 200
    assert confirmed.json()["esp32_confirmed"] is True


async def test_update_active_config_replaces_version(client, auth_admin):
    first = await _apply_config(client, auth_admin)
    first_version = first.json()["version"]

    updated = await client.put(
        "/api/config/active",
        json={"config_json": {"irrigation": {"enabled": True}}},
        headers=auth_admin,
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == first_version + 1

    # Only one active config must remain.
    active = await client.get("/api/config/active", headers=auth_admin)
    assert active.json()["config_json"]["irrigation"]["enabled"] is True


async def test_telemetry_ingest_and_latest(client):
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "temperature": 25.5,
        "humidity": 70.0,
        "pressure": 1013.0,
        "soil_adc": [2000, 2100, 1900, 2200, 2300, 2050],
        "soil_pct": [50.0, 48.0, 53.0, 45.0, 43.0, 48.0],
        "soil_ok": [True] * 6,
        "fan_1_state": True,
        "fan_2_state": False,
        "humidifier_1_state": False,
        "humidifier_2_state": False,
        "pump_state": False,
        "rssi": -65,
        "device_id": "field_esp32",
        "sequence": 1,
    }
    ingest = await client.post("/api/config/telemetry", json=payload)
    assert ingest.status_code == 201

    latest = await client.get("/api/config/telemetry/latest")
    assert latest.status_code == 200
    data = latest.json()
    assert data["temperature"] == 25.5
    assert len(data["soil_sensors"]) == 6
    assert data["soil_avg_row_a"] is not None
    assert data["soil_avg_row_b"] is not None
    assert data["soil_avg_general"] is not None


async def test_status_endpoint_does_not_crash(client, auth_admin):
    # Regression: /status used to raise NameError because Photo/Event were
    # not imported in the config router.
    resp = await client.get("/api/config/status", headers=auth_admin)
    assert resp.status_code == 200
    body = resp.json()
    assert "field_esp32_online" in body


async def test_telemetry_rejects_malformed_payload(client):
    resp = await client.post("/api/config/telemetry", json={"temperature": 20})
    assert resp.status_code == 400
