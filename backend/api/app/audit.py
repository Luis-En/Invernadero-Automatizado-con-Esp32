"""Audit trail helper used by admin routes and authentication."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuditLog, User
from app.security import client_ip

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    action: str,
    resource: str,
    *,
    user: Optional[User] = None,
    username: Optional[str] = None,
    request: Optional[Request] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist one audit entry. Never break the caller's request if it fails.

    Call this after the business transaction has committed. It uses the same
    session, so a failure rolls back only the audit insert.
    """
    if not settings.AUDIT_LOG_ENABLED:
        return

    ip = None
    user_agent = None
    if request is not None:
        try:
            ip = client_ip(request)
        except Exception:  # noqa: BLE001 - audit must not break the request
            ip = None
        user_agent = (request.headers.get("user-agent") or "")[:255] or None

    entry = AuditLog(
        timestamp=datetime.utcnow(),
        user_id=user.id if user is not None else None,
        username=(user.username if user is not None else username),
        action=action[:64],
        resource=resource[:160],
        ip=ip,
        user_agent=user_agent,
        details=details,
    )
    db.add(entry)
    try:
        await db.commit()
    except Exception:  # noqa: BLE001 - auditing must be best-effort
        await db.rollback()
        logger.exception("No se pudo escribir el registro de auditoría")
