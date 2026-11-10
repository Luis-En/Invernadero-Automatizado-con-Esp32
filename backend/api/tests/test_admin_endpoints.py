"""Role separation for /api/admin/* endpoints."""

CONFIG_PAYLOAD = {
    "config_json": {
        "hysteresis": {
            "temp": {"on_above": 30.0, "off_below": 27.5},
            "humidity": {"on_below": 60.0, "off_above": 68.0},
            "soil": {"on_below_pct": 35, "off_above_pct": 45},
        },
        "irrigation": {"enabled": False},
        "safety": {"max_on_seconds": {"pump": 900}},
    },
    "crop_id": None,
}


async def test_admin_endpoints_require_authentication(client):
    for method, path in (
        ("post", "/api/admin/actuators/control"),
        ("post", "/api/admin/crops"),
        ("post", "/api/admin/config"),
        ("post", "/api/admin/users"),
        ("get", "/api/admin/logs"),
        ("get", "/api/admin/health"),
    ):
        kwargs = {"json": {}} if method == "post" else {}
        resp = await getattr(client, method)(path, **kwargs)
        assert resp.status_code == 401, (path, resp.status_code)


async def test_viewer_cannot_use_admin_endpoints(client, auth_viewer):
    for method, path in (
        ("post", "/api/admin/actuators/control"),
        ("post", "/api/admin/crops"),
        ("post", "/api/admin/config"),
        ("post", "/api/admin/users"),
        ("get", "/api/admin/logs"),
    ):
        kwargs = {"json": {}} if method == "post" else {}
        resp = await getattr(client, method)(path, headers=auth_viewer, **kwargs)
        assert resp.status_code == 403, (path, resp.status_code)


async def test_admin_can_control_actuator(client, auth_admin, monkeypatch):
    monkeypatch.setattr(
        "app.routes.actuators.send_command",
        lambda actuator, state: {"actuator": actuator, "state": state, "queued": True},
    )
    resp = await client.post(
        "/api/admin/actuators/control",
        json={"actuator": "fan_1", "state": True},
        headers=auth_admin,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] is True


async def test_admin_can_apply_config(client, auth_admin):
    resp = await client.post(
        "/api/admin/config", json=CONFIG_PAYLOAD, headers=auth_admin
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["config_json"]["irrigation"]["enabled"] is False


async def test_admin_crop_crud(client, auth_admin):
    created = await client.post(
        "/api/admin/crops",
        json={
            "name": "admin_crop_test",
            "display_name": "Cultivo de prueba",
            "description": "Solo test",
        },
        headers=auth_admin,
    )
    assert created.status_code == 201, created.text
    crop_id = created.json()["id"]

    updated = await client.put(
        f"/api/admin/crops/{crop_id}",
        json={"display_name": "Cultivo actualizado"},
        headers=auth_admin,
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Cultivo actualizado"

    deleted = await client.delete(f"/api/admin/crops/{crop_id}", headers=auth_admin)
    assert deleted.status_code == 204


async def test_admin_health_returns_details(client, auth_admin):
    resp = await client.get("/api/admin/health", headers=auth_admin)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "database" in body
    assert "audit_enabled" in body


async def test_admin_can_create_user(client, auth_admin):
    resp = await client.post(
        "/api/admin/users",
        json={
            "username": "admin_created_user",
            "password": "AdminCreated123!",
            "role": "viewer",
        },
        headers=auth_admin,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "viewer"

