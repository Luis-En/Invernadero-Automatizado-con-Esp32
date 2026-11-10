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
        json={"username": "nope", "password": "StrongPass123!", "role": "viewer"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


async def test_admin_can_register(client, auth_admin):
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "password": "StrongPass123!",
            "email": "new@test.local",
            "role": "viewer",
        },
        headers=auth_admin,
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newuser"


async def test_register_rejects_short_password(client, auth_admin):
    resp = await client.post(
        "/api/auth/register",
        json={"username": "shortpass", "password": "password123", "role": "viewer"},
        headers=auth_admin,
    )
    assert resp.status_code == 422


async def test_register_rejects_weak_long_password(client, auth_admin):
    resp = await client.post(
        "/api/auth/register",
        json={"username": "weakpass", "password": "alllowercase123", "role": "viewer"},
        headers=auth_admin,
    )
    assert resp.status_code == 422


async def test_login_sets_httponly_cookie_and_logout_clears_it(client, admin_user):
    login = await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "adminpass123"},
    )
    assert login.status_code == 200
    set_cookie = login.headers.get("set-cookie", "")
    assert "greenhouse_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie

    # No Authorization header here: the cookie alone must authenticate.
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == admin_user.username

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert "greenhouse_session=" in logout.headers.get("set-cookie", "")

    after = await client.get("/api/auth/me")
    assert after.status_code == 401


async def test_cookie_auth_rejects_foreign_origin(client, admin_user):
    await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "adminpass123"},
    )
    blocked = await client.post(
        "/api/auth/logout", headers={"Origin": "https://evil.example.com"}
    )
    assert blocked.status_code == 403

    allowed = await client.post(
        "/api/auth/logout", headers={"Origin": "http://test"}
    )
    assert allowed.status_code == 204


async def test_login_rejects_foreign_origin(client, admin_user):
    resp = await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "adminpass123"},
        headers={"Origin": "https://evil.example.com"},
    )
    assert resp.status_code == 403


async def test_login_lockout_after_repeated_failures(client, admin_user, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES", 3)
    monkeypatch.setattr(settings, "LOGIN_LOCKOUT_SEC", 120)
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_FAILURES", 99)

    for _ in range(3):
        resp = await client.post(
            "/api/auth/login",
            json={"username": admin_user.username, "password": "wrong-password"},
        )
        assert resp.status_code == 401

    locked = await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "adminpass123"},
    )
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0
    assert "Demasiados intentos" in locked.json()["detail"]


async def test_lockout_applies_to_unknown_usernames(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES", 2)
    monkeypatch.setattr(settings, "LOGIN_LOCKOUT_SEC", 120)
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_FAILURES", 99)

    for _ in range(2):
        resp = await client.post(
            "/api/auth/login",
            json={"username": "does-not-exist", "password": "wrong-password"},
        )
        assert resp.status_code == 401

    locked = await client.post(
        "/api/auth/login",
        json={"username": "does-not-exist", "password": "wrong-password"},
    )
    assert locked.status_code == 429


async def test_successful_login_clears_failure_counter(client, admin_user, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES", 3)
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_FAILURES", 99)

    for _ in range(2):
        resp = await client.post(
            "/api/auth/login",
            json={"username": admin_user.username, "password": "wrong-password"},
        )
        assert resp.status_code == 401

    ok = await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "adminpass123"},
    )
    assert ok.status_code == 200

    for _ in range(2):
        resp = await client.post(
            "/api/auth/login",
            json={"username": admin_user.username, "password": "wrong-password"},
        )
        assert resp.status_code == 401


async def test_cors_only_allows_configured_origins(client):
    evil = await client.options(
        "/api/public/telemetry",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert evil.status_code in (200, 400)
    assert "access-control-allow-origin" not in evil.headers

    allowed = await client.options(
        "/api/public/telemetry",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_security_headers_on_api(client):
    resp = await client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"

    api_resp = await client.get("/api/auth/me")
    assert api_resp.status_code == 401
    assert api_resp.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in api_resp.headers["content-security-policy"]


async def test_slowapi_login_rate_limit(client, admin_user, monkeypatch):
    from app.config import settings
    from app.rate_limit import limiter

    # Disable the persistent lockout so this test isolates the SlowAPI layer.
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES", 999)
    monkeypatch.setattr(settings, "LOGIN_IP_MAX_FAILURES", 999)

    limiter.reset()
    limiter.enabled = True
    try:
        statuses = []
        for _ in range(6):
            resp = await client.post(
                "/api/auth/login",
                json={"username": admin_user.username, "password": "wrong-password"},
            )
            statuses.append(resp.status_code)
        assert statuses == [401, 401, 401, 401, 401, 429]
    finally:
        limiter.enabled = False
        limiter.reset()


async def test_login_requires_https_header_in_production(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "REQUIRE_HTTPS", "true")
    blocked = await client.get("/api/auth/me")
    assert blocked.status_code == 403
    assert "HTTPS" in blocked.json()["detail"]

    allowed = await client.get(
        "/api/auth/me", headers={"X-Forwarded-Proto": "https"}
    )
    assert allowed.status_code == 401



def test_client_ip_ignores_spoofed_forwarding_headers_from_public_peers():
    from starlette.requests import Request

    from app.security import client_ip

    def request_from(peer, headers):
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [
                    (key.lower().encode(), value.encode()) for key, value in headers.items()
                ],
                "client": (peer, 1234),
                "server": ("test", 80),
                "scheme": "http",
                "query_string": b"",
            }
        )

    public = request_from("8.8.8.8", {"x-real-ip": "1.2.3.4"})
    assert client_ip(public) == "8.8.8.8"

    proxy = request_from("172.19.0.5", {"x-real-ip": "198.51.100.7"})
    assert client_ip(proxy) == "198.51.100.7"

    malformed = request_from("10.0.0.3", {"x-real-ip": "not-an-ip"})
    assert client_ip(malformed) == "10.0.0.3"


def test_production_disables_api_docs(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert settings.docs_enabled is False
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert settings.docs_enabled is True


async def test_legacy_sha256_password_is_upgraded_on_login(client, db):
    from passlib.hash import sha256_crypt

    from app.models import User

    user = User(
        username="legacy_hash",
        email="legacy@test.local",
        hashed_password=sha256_crypt.hash("legacy-password-123"),
        role="viewer",
        is_active=True,
    )
    db.add(user)
    await db.commit()

    login = await client.post(
        "/api/auth/login",
        json={"username": "legacy_hash", "password": "legacy-password-123"},
    )
    assert login.status_code == 200

    await db.refresh(user)
    assert user.hashed_password.startswith("$2b$")
