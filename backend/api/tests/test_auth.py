"""Auth and permission tests."""


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_login_ok(client, admin_user):
    resp = await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "adminpass123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["user"]["role"] == "admin"


async def test_login_bad_password_returns_401(client, admin_user):
    resp = await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_login_short_password_still_401_not_422(client, admin_user):
    # A dedicated LoginRequest schema must not reject short passwords with 422.
    resp = await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "x"},
    )
    assert resp.status_code == 401


async def test_me_requires_auth(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_returns_user(client, admin_user, auth_admin):
    resp = await client.get("/api/auth/me", headers=auth_admin)
    assert resp.status_code == 200
    assert resp.json()["username"] == admin_user.username


async def test_register_requires_admin(client, admin_user, viewer_token):
    resp = await client.post(
        "/api/auth/register",
        json={"username": "nope", "password": "password123", "role": "viewer"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


async def test_admin_can_register(client, auth_admin):
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "password": "password123",
            "email": "new@test.local",
            "role": "viewer",
        },
        headers=auth_admin,
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newuser"
