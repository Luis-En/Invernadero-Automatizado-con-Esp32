"""Irrigation assessment and Web Push subscription tests."""

from datetime import datetime

import pytest

from app.irrigation import assess_irrigation, thresholds_from_config


def test_thresholds_fall_back_and_repair_inverted_config():
    assert thresholds_from_config(None) == (35.0, 45.0)
    # OFF <= ON would make the pump chatter; it is moved 10 points above ON.
    on, off = thresholds_from_config({"hysteresis": {"soil": {"on_below_pct": 40, "off_above_pct": 30}}})
    assert on == 40.0
    assert off == 50.0


@pytest.mark.parametrize(
    "values,expected",
    [
        ([20.0] * 6, True),
        ([36.0] * 6, False),
        ([None, 20.0], True),
    ],
)
def test_assess_enters_needed_state(values, expected):
    assessment = assess_irrigation(values, None, {"hysteresis": {"soil": {"on_below_pct": 35, "off_above_pct": 45}}})
    assert assessment.needed is expected
    assert assessment.known is True


def test_assess_hysteresis_keeps_alarm_until_recovered():
    config = {"hysteresis": {"soil": {"on_below_pct": 35, "off_above_pct": 45}}}
    # 40% is above the ON threshold but below OFF, so an active episode stays.
    assert assess_irrigation([40.0], [True], config, previously_needed=True).needed is True
    assert assess_irrigation([45.0], [True], config, previously_needed=True).needed is False


def test_assess_rejects_invalid_flags_and_out_of_range():
    assessment = assess_irrigation([None, -5, 120, 20.0], [True, True, True, False])
    assert assessment.known is False
    assert assessment.soil_avg is None


async def test_notification_config_without_keys(client, auth_admin):
    response = await client.get("/api/notifications/config", headers=auth_admin)
    assert response.status_code == 200
    body = response.json()
    assert body["push_supported"] is False
    assert body["vapid_public_key"] is None
    assert body["soil_on_below_pct"] == 35
    assert body["soil_off_above_pct"] == 45


async def test_notification_config_requires_auth(client):
    response = await client.get("/api/notifications/config")
    assert response.status_code in (401, 403)


async def test_subscribe_upserts_and_unsubscribes(client, auth_admin, db):
    from sqlalchemy import select

    from app.models import PushSubscription

    payload = {
        "endpoint": "https://push.example.com/subscription/abc123",
        "keys": {
            "p256dh": "B" * 40,
            "auth": "a" * 16,
        },
        "user_agent": "pytest",
    }

    first = await client.post("/api/notifications/subscribe", json=payload, headers=auth_admin)
    assert first.status_code == 201, first.text

    payload["keys"]["p256dh"] = "C" * 40
    second = await client.post("/api/notifications/subscribe", json=payload, headers=auth_admin)
    assert second.status_code == 201, second.text

    result = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == payload["endpoint"])
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].p256dh == "C" * 40

    deleted = await client.request(
        "DELETE",
        "/api/notifications/subscribe",
        json={"endpoint": payload["endpoint"]},
        headers=auth_admin,
    )
    assert deleted.status_code == 204

    remaining = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == payload["endpoint"])
    )
    assert remaining.scalars().all() == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://push.example.com/abc",
        "https://127.0.0.1/abc",
        "https://10.0.0.5/abc",
        "https://localhost/abc",
        "https://printer.local/abc",
        "not-a-url",
    ],
)
async def test_subscribe_rejects_unsafe_endpoints(client, auth_admin, endpoint):
    response = await client.post(
        "/api/notifications/subscribe",
        json={"endpoint": endpoint, "keys": {"p256dh": "B" * 40, "auth": "a" * 16}},
        headers=auth_admin,
    )
    assert response.status_code in (401, 422)


async def test_test_notification_without_vapid_returns_503(client, auth_admin):
    response = await client.post("/api/notifications/test", headers=auth_admin)
    assert response.status_code == 503


async def test_status_does_not_alert_from_stale_telemetry(client, auth_admin, device_headers):
    from datetime import timedelta

    payload = {
        "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z",
        "temperature": 25.0,
        "humidity": 70.0,
        "pressure": 1013.0,
        "soil_adc": [2000] * 6,
        "soil_pct": [10.0] * 6,
        "soil_ok": [True] * 6,
        "fan_1_state": False,
        "fan_2_state": False,
        "humidifier_1_state": False,
        "humidifier_2_state": False,
        "pump_state": False,
        "rssi": -60,
        "device_id": "field_esp32",
        "sequence": 3,
    }
    ingest = await client.post("/api/config/telemetry", json=payload, headers=device_headers)
    assert ingest.status_code == 201

    status = await client.get("/api/config/status", headers=auth_admin)
    assert status.status_code == 200
    body = status.json()
    assert body["telemetry_stale"] is True
    assert body["irrigation_needed"] is False
    assert body["soil_avg_pct"] == 10.0


async def test_status_reports_irrigation_need(client, auth_admin, device_headers):
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "temperature": 25.0,
        "humidity": 70.0,
        "pressure": 1013.0,
        "soil_adc": [2000] * 6,
        "soil_pct": [18.0, 20.0, 22.0, 19.0, 21.0, 23.0],
        "soil_ok": [True] * 6,
        "fan_1_state": False,
        "fan_2_state": False,
        "humidifier_1_state": False,
        "humidifier_2_state": False,
        "pump_state": False,
        "rssi": -60,
        "device_id": "field_esp32",
        "sequence": 2,
    }
    ingest = await client.post("/api/config/telemetry", json=payload, headers=device_headers)
    assert ingest.status_code == 201

    status = await client.get("/api/config/status", headers=auth_admin)
    assert status.status_code == 200
    body = status.json()
    assert body["irrigation_needed"] is True
    assert body["soil_avg_pct"] == pytest.approx(20.5, abs=0.1)
    assert body["soil_threshold_pct"] == 35
    assert body["valid_soil_sensors"] == 6
