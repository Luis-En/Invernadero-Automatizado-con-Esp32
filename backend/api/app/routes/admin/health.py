from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import ActiveConfig, Photo, Reading
from app.routes.public import public_manager

router = APIRouter(prefix="/health", tags=["admin-health"])


@router.get("")
async def admin_health(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    latest = await db.execute(select(Reading).order_by(desc(Reading.timestamp)).limit(1))
    reading = latest.scalar_one_or_none()
    photo_result = await db.execute(select(Photo).order_by(desc(Photo.timestamp)).limit(1))
    photo = photo_result.scalar_one_or_none()
    config_result = await db.execute(
        select(ActiveConfig)
        .where(ActiveConfig.is_active == True)  # noqa: E712
        .order_by(desc(ActiveConfig.version))
        .limit(1)
    )
    active_config = config_result.scalar_one_or_none()
    now = datetime.utcnow()
    return {
        "status": "ok",
        "service": "greenhouse-api",
        "environment": settings.ENVIRONMENT,
        "database": "ok",
        "field_online": bool(
            reading and now - reading.timestamp <= timedelta(minutes=2)
        ),
        "last_telemetry": reading.timestamp.isoformat() if reading else None,
        "last_photo": photo.timestamp.isoformat() if photo else None,
        "active_config_version": active_config.version if active_config else None,
        "audit_enabled": bool(settings.AUDIT_LOG_ENABLED),
        "rate_limit_enabled": bool(settings.RATE_LIMIT_ENABLED),
        "push_configured": bool(settings.push_configured),
        "public_ws_connections": len(public_manager.connections),
    }
