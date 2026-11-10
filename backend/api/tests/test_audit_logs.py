"""Audit trail for auth and administrative actions."""

from sqlalchemy import select


async def test_failed_login_is_audited(client, admin_user, db):
    from app.models import AuditLog

    resp = await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "wrong-password"},
    )
    assert resp.status_code == 401

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action == "auth.login_failed")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.username == admin_user.username
    assert entry.ip is not None


async def test_successful_login_is_audited(client, admin_user, db):
    from app.models import AuditLog

    resp = await client.post(
        "/api/auth/login",
        json={"username": admin_user.username, "password": "adminpass123"},
    )
    assert resp.status_code == 200

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action == "auth.login_success")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.user_id == admin_user.id


async def test_admin_action_is_audited_and_filterable(client, auth_admin, db, monkeypatch):
    from app.models import AuditLog

    monkeypatch.setattr(
        "app.routes.actuators.send_command",
        lambda actuator, state: {"actuator": actuator, "state": state, "queued": True},
    )
    resp = await client.post(
        "/api/admin/actuators/control",
        json={"actuator": "fan_2", "state": False},
        headers=auth_admin,
    )
    assert resp.status_code == 200

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action == "actuator.control")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.resource == "actuator:fan_2"
    assert entry.details["state"] is False

    listed = await client.get(
        "/api/admin/logs?action=actuator.control&limit=10", headers=auth_admin
    )
    assert listed.status_code == 200
    assert any(row["action"] == "actuator.control" for row in listed.json())


async def test_audit_logs_can_be_filtered_by_username(client, auth_admin, admin_user, db):
    result = await client.get(
        f"/api/admin/logs?username={admin_user.username}&limit=10",
        headers=auth_admin,
    )
    assert result.status_code == 200
    assert all(row["username"] == admin_user.username for row in result.json())


async def test_user_creation_is_audited(client, auth_admin, db):
    from app.models import AuditLog

    created = await client.post(
        "/api/auth/register",
        json={
            "username": "audited_user",
            "password": "AuditedPass123!",
            "role": "viewer",
        },
        headers=auth_admin,
    )
    assert created.status_code == 201

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action == "user.create")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.details["username"] == "audited_user"

