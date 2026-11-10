"""Endpoints for the browser Web Push subscription lifecycle."""

import ipaddress
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_active_user
from app.irrigation import thresholds_from_config
from app.models import ActiveConfig, PushSubscription
from app.notifications import get_vapid_public_key, send_push_to_all
from app.schemas import (
    NotificationConfig,
    PushSubscriptionCreate,
    PushSubscriptionDelete,
    PushSubscriptionResponse,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _validate_push_endpoint(endpoint: str) -> None:
    """Reject obvious SSRF targets.

    A push endpoint is fetched by the server, so an authenticated user must
    not be able to point it at a loopback/LAN address. Real push services are
    always public HTTPS hosts.
    """
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(422, "El endpoint de push debe ser una URL HTTPS válida")

    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise HTTPException(422, "Endpoint de push no permitido")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    ):
        raise HTTPException(422, "Endpoint de push no permitido")


async def _active_config_json(db: AsyncSession) -> dict | None:
    result = await db.execute(
        select(ActiveConfig)
        .where(ActiveConfig.is_active == True)  # noqa: E712
        .order_by(desc(ActiveConfig.version))
        .limit(1)
    )
    config = result.scalar_one_or_none()
    return config.config_json if config else None


@router.get("/config", response_model=NotificationConfig)
async def notification_config(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_active_user),
):
    config_json = await _active_config_json(db)
    on_below, off_above = thresholds_from_config(config_json)
    public_key = get_vapid_public_key() if settings.push_configured else None

    return NotificationConfig(
        enabled=bool(settings.NOTIFICATIONS_ENABLED),
        push_supported=bool(public_key and settings.push_configured),
        vapid_public_key=public_key,
        check_interval_sec=max(15, int(settings.IRRIGATION_CHECK_SEC)),
        reminder_hours=float(settings.IRRIGATION_REMINDER_HOURS),
        soil_on_below_pct=on_below,
        soil_off_above_pct=off_above,
    )


@router.post("/subscribe", response_model=PushSubscriptionResponse, status_code=201)
async def subscribe(
    payload: PushSubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_active_user),
):
    _validate_push_endpoint(payload.endpoint)

    result = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    )
    subscription = result.scalar_one_or_none()

    if subscription is None:
        subscription = PushSubscription(
            user_id=user.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            user_agent=payload.user_agent,
        )
        db.add(subscription)
    else:
        # The same browser may re-subscribe after clearing storage; refresh the
        # keys and ownership instead of creating a duplicate endpoint.
        subscription.user_id = user.id
        subscription.p256dh = payload.keys.p256dh
        subscription.auth = payload.keys.auth
        subscription.user_agent = payload.user_agent
        subscription.is_active = True

    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.delete("/subscribe", status_code=204)
async def unsubscribe(
    payload: PushSubscriptionDelete,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_active_user),
):
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.endpoint == payload.endpoint,
            PushSubscription.user_id == user.id,
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is not None:
        await db.delete(subscription)
        await db.commit()
    return Response(status_code=204)


@router.post("/test")
async def send_test_notification(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_active_user),
):
    if not settings.push_configured:
        raise HTTPException(
            503,
            "El servidor no tiene claves VAPID configuradas. "
            "Ejecuta scripts/generate_vapid_keys.sh y reinicia la API.",
        )

    result = await send_push_to_all(
        db,
        {
            "title": "🌱 Invernadero — prueba",
            "body": "Las notificaciones de riego están funcionando en este dispositivo.",
            "url": "/",
            "tag": "greenhouse-test",
        },
        user_id=user.id,
    )

    if result.get("skipped"):
        raise HTTPException(503, "Las notificaciones push están desactivadas")
    if result.get("sent", 0) == 0:
        raise HTTPException(
            404,
            "No hay dispositivos suscritos para este usuario. "
            "Activa las notificaciones primero.",
        )
    return {"status": "ok", **result}
