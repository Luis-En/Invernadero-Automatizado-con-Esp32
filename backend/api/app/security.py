"""Security helpers for login throttling and client-IP resolution."""

import asyncio
import hashlib
import ipaddress
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuthThrottle

# How long a throttle row is useful. Rows are pruned opportunistically.
THROTTLE_RETENTION_DAYS = 7

# SQLite has no row-level locking. A single-process asyncio lock prevents two
# concurrent failed logins from racing the select/insert on a new counter row.
_throttle_lock = asyncio.Lock()


def client_ip(request: Request) -> str:
    """Return the real client IP without trusting arbitrary spoofed headers.

    Nginx runs in a private Docker network and sets X-Real-IP. We only honour
    forwarding headers when the direct peer is private/loopback; a public
    client connecting directly to :8000 cannot forge its address.
    """
    peer = request.client.host if request.client else "unknown"
    try:
        peer_address = ipaddress.ip_address(peer)
    except ValueError:
        # Test clients use a hostname such as "testclient".
        return peer[:64]

    if not any(peer_address in network for network in settings.trusted_proxy_networks):
        return peer

    candidate = (request.headers.get("x-real-ip") or "").strip()
    if not candidate:
        forwarded = request.headers.get("x-forwarded-for") or ""
        if forwarded:
            candidate = forwarded.split(",")[0].strip()

    if candidate:
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            pass
    return peer


def hash_ip(value: str) -> str:
    """Non-reversible representation for audit events."""
    salt = (settings.JWT_SECRET_KEY or "greenhouse").encode("utf-8")
    return hashlib.sha256(salt + value.encode("utf-8")).hexdigest()[:16]


async def get_active_lock(
    db: AsyncSession, scope: str, key: str, now: datetime
) -> Optional[datetime]:
    result = await db.execute(
        select(AuthThrottle).where(
            AuthThrottle.scope == scope,
            AuthThrottle.key == key,
        )
    )
    row = result.scalar_one_or_none()
    if row and row.locked_until and row.locked_until > now:
        return row.locked_until
    return None


async def register_failure(
    db: AsyncSession,
    scope: str,
    key: str,
    now: datetime,
    max_failures: int,
    window_seconds: int,
    lockout_seconds: int,
) -> Tuple[bool, Optional[datetime]]:
    """Count one failure. Returns (newly_locked, locked_until)."""
    async with _throttle_lock:
        return await _register_failure_locked(
            db, scope, key, now, max_failures, window_seconds, lockout_seconds
        )


async def _register_failure_locked(
    db: AsyncSession,
    scope: str,
    key: str,
    now: datetime,
    max_failures: int,
    window_seconds: int,
    lockout_seconds: int,
) -> Tuple[bool, Optional[datetime]]:
    result = await db.execute(
        select(AuthThrottle).where(
            AuthThrottle.scope == scope,
            AuthThrottle.key == key,
        )
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = AuthThrottle(
            scope=scope,
            key=key,
            failures=0,
            window_start=now,
            updated_at=now,
        )
        db.add(row)

    if row.locked_until and row.locked_until > now:
        # Already locked: do not extend the punishment on every request.
        return False, row.locked_until

    if row.window_start is None or (now - row.window_start).total_seconds() > window_seconds:
        row.failures = 0
        row.window_start = now

    row.failures = (row.failures or 0) + 1
    row.updated_at = now

    locked_until: Optional[datetime] = None
    if row.failures >= max(1, max_failures):
        locked_until = now + timedelta(seconds=max(1, lockout_seconds))
        row.locked_until = locked_until
        row.failures = 0

    await db.commit()
    return locked_until is not None, locked_until


async def clear_failures(db: AsyncSession, scope: str, key: str) -> None:
    async with _throttle_lock:
        await db.execute(
            delete(AuthThrottle).where(
                AuthThrottle.scope == scope,
                AuthThrottle.key == key,
            )
        )
        await db.commit()


async def prune_old_attempts(db: AsyncSession, now: datetime) -> None:
    cutoff = now - timedelta(days=THROTTLE_RETENTION_DAYS)
    async with _throttle_lock:
        await db.execute(delete(AuthThrottle).where(AuthThrottle.updated_at < cutoff))
        await db.commit()
