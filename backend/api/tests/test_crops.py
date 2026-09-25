"""Crop catalogue and params tests."""


async def test_crops_require_auth(client):
    resp = await client.get("/api/crops")
    assert resp.status_code == 401


async def test_seeded_crops_available(client, auth_admin):
    resp = await client.get("/api/crops", headers=auth_admin)
    assert resp.status_code == 200
    names = {c["name"] for c in resp.json()}
    assert {"tomate", "pepino", "lechuga"} <= names


async def test_crop_param_bounds_validated(client, auth_admin):
    crop = await client.post(
        "/api/crops",
        json={"name": "test_bounds", "display_name": "Test Bounds"},
        headers=auth_admin,
    )
    crop_id = crop.json()["id"]
    resp = await client.post(
        f"/api/crops/{crop_id}/params",
        json={"crop_id": crop_id, "soil_moisture_min_pct": 150},
        headers=auth_admin,
    )
    assert resp.status_code == 422


async def test_crop_crud_roundtrip(client, auth_admin):
    created = await client.post(
        "/api/crops",
        json={"name": "test_crud", "display_name": "Test CRUD"},
        headers=auth_admin,
    )
    assert created.status_code == 201
    crop_id = created.json()["id"]

    params = await client.post(
        f"/api/crops/{crop_id}/params",
        json={
            "crop_id": crop_id,
            "temp_min": 15.0,
            "temp_max": 30.0,
            "humidity_min": 60.0,
            "humidity_max": 80.0,
        },
        headers=auth_admin,
    )
    assert params.status_code == 201

    full = await client.get(f"/api/crops/{crop_id}", headers=auth_admin)
    assert full.status_code == 200
    assert full.json()["params"]["temp_min"] == 15.0

    updated = await client.put(
        f"/api/crops/{crop_id}", json={"description": "changed"}, headers=auth_admin
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "changed"

    deleted = await client.delete(f"/api/crops/{crop_id}", headers=auth_admin)
    assert deleted.status_code == 204


async def test_viewer_cannot_create_crop(client, auth_viewer):
    resp = await client.post(
        "/api/crops",
        json={"name": "nope", "display_name": "Nope"},
        headers=auth_viewer,
    )
    assert resp.status_code == 403
