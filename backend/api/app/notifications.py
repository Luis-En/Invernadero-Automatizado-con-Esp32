"""Web Push delivery and the background irrigation watcher.

The watcher is intentionally simple and single-process: it polls the latest
reading, applies the same hysteresis as the actuator logic, and pushes one
notification when the soil crosses into "needs water". While the soil stays
dry it reminds at most once per configured interval. Uvicorn runs one worker
by default, which is what this deployment expects.
"""

import asyncio
import base64
import json
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

from sqlalchemy import desc, select
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import AsyncSessionLocal
from app.irrigation import assess_irrigation, soil_from_reading, thresholds_from_config
from app.models import ActiveConfig, Crop, Event, PushSubscription, Reading

logger = logging.getLogger(__name__)

_watch_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None


def _epoch(value: datetime) -> float:
    """Seconds since epoch for a naive UTC datetime (no local-time guessing)."""
    return (value - datetime(1970, 1, 1)).total_seconds()


@lru_cache(maxsize=1)
def get_vapid_public_key() -> Optional[str]:
    """Return the VAPID public key as base64url (applicationServerKey format)."""
    if not settings.push_configured:
        return None
    try:
        from cryptography.hazmat.primitives import serialization

        private_key = serialization.load_pem_private_key(
            settings.vapid_private_key_path.read_bytes(),
            password=None,
        )
        numbers = private_key.public_key().public_numbers()
        raw = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    except Exception:  # noqa: BLE001 - a broken key must not crash the API
        logger.exception("No se pudo leer la clave pública VAPID")
        return None


def ensure_vapid_keys() -> None:
    """Generate a P-256 VAPID pair once when explicitly enabled.

    Dokploy/named-volume deployments start with an empty secrets volume; this
    keeps push working without copying .pem files into the repository. The
    private key is written with mode 600. Existing keys are never overwritten.
    """
    if not settings.VAPID_AUTO_GENERATE:
        return
    private_path = settings.vapid_private_key_path
    public_path = settings.vapid_public_key_path
    if private_path.is_file() and public_path.is_file():
        return

    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        private_key = ec.generate_private_key(ec.SECP256R1())
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        private_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_bytes(private_pem)
        private_path.chmod(0o600)
        public_path.write_bytes(public_pem)
        public_path.chmod(0o644)
        get_vapid_public_key.cache_clear()
        logger.warning("Se generaron claves VAPID nuevas en %s", private_path.parent)
    except Exception:  # noqa: BLE001 - push is optional; do not block startup
        logger.exception("No se pudieron generar las claves VAPID")


def _send_push_blocking(subscription: PushSubscription, payload: dict) -> str:
    """Send one push. Returns 'ok', 'gone' (unsubscribe) or 'error'."""
    try:
        from pywebpush import WebPushException, webpush

        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=str(settings.vapid_private_key_path),
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            timeout=10,
        )
        return "ok"
    except Exception as exc:  # noqa: BLE001 - pywebpush raises several types
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code in (404, 410):
            return "gone"
        logger.warning("Fallo al enviar push (%s): %s", status_code or "sin respuesta", exc)
        return "error"


async def send_push_to_all(db, payload: dict, user_id: Optional[int] = None) -> dict:
    """Send a payload to active subscriptions, pruning dead endpoints.

    ``user_id`` limits delivery to one account (used by the test button).
    """
    if not settings.push_configured:
        return {"sent": 0, "pruned": 0, "failed": 0, "skipped": True}

    query = select(PushSubscription).where(
        PushSubscription.is_active == True  # noqa: E712
    )
    if user_id is not None:
        query = query.where(PushSubscription.user_id == user_id)
    result = await db.execute(query)
    subscriptions = result.scalars().all()
    sent = pruned = failed = 0

    for subscription in subscriptions:
        outcome = await run_in_threadpool(_send_push_blocking, subscription, payload)
        if outcome == "ok":
            sent += 1
            subscription.last_seen = datetime.utcnow()
        elif outcome == "gone":
            pruned += 1
            subscription.is_active = False
        else:
            failed += 1

    if sent or pruned:
        await db.commit()
    return {"sent": sent, "pruned": pruned, "failed": failed, "skipped": False}


async def _broadcast_event(event: Event) -> None:
    try:
        from app.routes.config import manager

        await manager.broadcast(
            {
                "type": "event",
                "data": {
                    "id": event.id,
                    "severity": event.severity,
                    "code": event.code,
                    "message": event.message,
                    "timestamp": event.timestamp.isoformat(),
                },
            }
        )
    except Exception:  # noqa: BLE001 - a missing socket must not stop the watcher
        pass


def _push_payload(crop_name: Optional[str], soil_avg: float, threshold: float, critical: bool) -> dict:
    crop = crop_name or "el invernadero"
    return {
        "title": f"{'🚨' if critical else '💧'} Riego necesario — {crop}",
        "body": (
            f"La humedad media del suelo es {soil_avg:.0f}% y el umbral es {threshold:.0f}%. "
            "Revisa la bomba y la fuente de agua."
        ),
        "url": "/",
        "tag": "irrigation-needed",
        "critical": critical,
    }


async def check_irrigation_once(state: dict) -> None:
    """One watcher iteration. Exposed for tests and for manual diagnostics."""
    now = datetime.utcnow()

    async with AsyncSessionLocal() as db:
        reading_result = await db.execute(select(Reading).order_by(desc(Reading.timestamp)).limit(1))
        reading = reading_result.scalar_one_or_none()
        if reading is None:
            return
        if (now - reading.timestamp) > timedelta(minutes=settings.IRRIGATION_MAX_AGE_MIN):
            logger.debug(
                "Riego: telemetría con más de %s min, no se evalúa",
                settings.IRRIGATION_MAX_AGE_MIN,
            )
            return

        config_result = await db.execute(
            select(ActiveConfig)
            .where(ActiveConfig.is_active == True)  # noqa: E712
            .order_by(desc(ActiveConfig.version))
            .limit(1)
        )
        active_config = config_result.scalar_one_or_none()
        config_json = active_config.config_json if active_config else None

        crop_name = None
        if active_config and active_config.crop_id:
            crop_result = await db.execute(select(Crop).where(Crop.id == active_config.crop_id))
            crop = crop_result.scalar_one_or_none()
            crop_name = crop.display_name if crop else None

        values, flags = soil_from_reading(reading)

        assessment = assess_irrigation(
            values,
            flags,
            config_json,
            previously_needed=bool(state.get("needed")),
            min_valid_sensors=settings.IRRIGATION_MIN_VALID_SENSORS,
        )

        if not assessment.known:
            logger.debug("Riego: %s", assessment.reason)
            return

        if not state.get("initialized"):
            # On restart, adopt a recent unresolved alert instead of pushing
            # twice — but only if the soil is still dry right now.
            state["initialized"] = True
            if assessment.needed:
                last_event_result = await db.execute(
                    select(Event)
                    .where(Event.code == "IRRIGATION_NEEDED")
                    .order_by(desc(Event.timestamp))
                    .limit(1)
                )
                last_event = last_event_result.scalar_one_or_none()
                recent = last_event is not None and (
                    now - last_event.timestamp
                ) < timedelta(hours=settings.IRRIGATION_REMINDER_HOURS)
                if recent:
                    state["needed"] = True
                    state["last_notified"] = _epoch(last_event.timestamp)
                    assessment = assess_irrigation(
                        values,
                        flags,
                        config_json,
                        previously_needed=True,
                        min_valid_sensors=settings.IRRIGATION_MIN_VALID_SENSORS,
                    )

        state["soil_avg"] = assessment.soil_avg
        on_below, _ = thresholds_from_config(config_json)
        critical = assessment.soil_avg is not None and assessment.soil_avg <= on_below - 10

        if assessment.needed and not state.get("needed"):
            state["needed"] = True
            message = (
                f"Riego necesario: humedad del suelo {assessment.soil_avg:.0f}% "
                f"(umbral {assessment.on_below:.0f}%)."
            )
            event = Event(
                timestamp=now,
                severity="critical" if critical else "warning",
                code="IRRIGATION_NEEDED",
                message=message,
                details={
                    "soil_avg_pct": round(assessment.soil_avg, 2),
                    "threshold_pct": assessment.on_below,
                    "off_above_pct": assessment.off_above,
                    "valid_sensors": assessment.valid_sensors,
                    "crop": crop_name,
                },
            )
            db.add(event)
            await db.commit()
            await db.refresh(event)
            await _broadcast_event(event)
            result = await send_push_to_all(
                db,
                _push_payload(crop_name, assessment.soil_avg, assessment.on_below, critical),
            )
            state["last_notified"] = _epoch(now)
            logger.info(
                "Alerta de riego %s (push: %s)", message, result
            )
            return

        if assessment.needed:
            last_notified = float(state.get("last_notified") or 0)
            if _epoch(now) - last_notified >= settings.IRRIGATION_REMINDER_HOURS * 3600:
                result = await send_push_to_all(
                    db,
                    _push_payload(crop_name, assessment.soil_avg, assessment.on_below, critical),
                )
                state["last_notified"] = _epoch(now)
                logger.info("Recordatorio de riego enviado (push: %s)", result)
            return

        if state.get("needed"):
            state["needed"] = False
            state["last_notified"] = 0
            event = Event(
                timestamp=now,
                severity="info",
                code="IRRIGATION_RESOLVED",
                message=(
                    f"Humedad del suelo recuperada: {assessment.soil_avg:.0f}% "
                    f"(>= {assessment.off_above:.0f}%)."
                ),
                details={
                    "soil_avg_pct": round(assessment.soil_avg, 2),
                    "off_above_pct": assessment.off_above,
                    "crop": crop_name,
                },
            )
            db.add(event)
            await db.commit()
            await db.refresh(event)
            await _broadcast_event(event)
            logger.info("Riego resuelto: %.1f%%", assessment.soil_avg)


async def _watch_loop(stop_event: asyncio.Event) -> None:
    state: dict = {"initialized": False, "needed": False, "last_notified": 0}
    interval = max(15, int(settings.IRRIGATION_CHECK_SEC))
    logger.info("Vigilancia de riego activa cada %s s", interval)

    while not stop_event.is_set():
        try:
            await check_irrigation_once(state)
        except Exception:  # noqa: BLE001 - the watcher must survive a bad row
            logger.exception("Error en la vigilancia de riego")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


def start_irrigation_watcher() -> Optional[asyncio.Task]:
    global _watch_task, _stop_event
    if not settings.NOTIFICATIONS_ENABLED:
        logger.info("Notificaciones desactivadas por configuración")
        return None
    if _watch_task and not _watch_task.done():
        return _watch_task

    _stop_event = asyncio.Event()
    _watch_task = asyncio.create_task(_watch_loop(_stop_event))
    return _watch_task


async def stop_irrigation_watcher() -> None:
    global _watch_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _watch_task is not None:
        try:
            await asyncio.wait_for(_watch_task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _watch_task.cancel()
    _watch_task = None
    _stop_event = None
