from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, StrictBool
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.dependencies import get_admin_user
from app.config import settings
from app.models import ActiveConfig, ActuatorLog, Reading
from app.serial_commands import send_command, CommandTimeout, CommandUnavailable, CommandRejected
from app.rate_limit import limiter
from app.realtime import broadcast_actuator_state

router = APIRouter(prefix="/api/actuators", tags=["actuators"])
ActuatorName = Literal["fan_1", "fan_2", "humidifier_1", "pump"]


class ActuatorCommand(BaseModel):
    state: StrictBool


@router.post("/{actuator}/command")
@limiter.limit(settings.RATE_LIMIT_ACTUATOR)
async def command_actuator(actuator: ActuatorName, command: ActuatorCommand,
                           request: Request,
                           db: AsyncSession = Depends(get_db),
                           admin=Depends(get_admin_user)):
    return await perform_actuator_command(actuator, command.state, db, admin)


async def perform_actuator_command(actuator: str, state: bool, db: AsyncSession, admin):
    """Shared by the legacy route and /api/admin/actuators/control."""
    # OFF must always remain available, even with irrigation disabled.
    if actuator == "pump" and state:
        result = await db.execute(select(ActiveConfig).where(
            ActiveConfig.is_active == True).order_by(desc(ActiveConfig.version)).limit(1))
        config = result.scalar_one_or_none()
        if not config or not config.config_json.get("irrigation", {}).get("enabled", False):
            raise HTTPException(409, "Habilite el riego antes de encender la bomba")
    try:
        ack = await run_in_threadpool(send_command, actuator, state)
    except CommandRejected as exc:
        raise HTTPException(409, str(exc)) from exc
    except CommandUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except CommandTimeout as exc:
        raise HTTPException(504, str(exc)) from exc

    confirmed_state = bool(ack.get("state", state)) if isinstance(ack, dict) else bool(state)
    confirmed_at = datetime.now(timezone.utc).isoformat()

    # Every accepted manual command is auditable. Automatic decisions are
    # logged by the control loop; this covers the operator path.
    db.add(ActuatorLog(
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        actuator=actuator,
        state=confirmed_state,
        triggered_by="manual",
        reason=f"Comando manual confirmado por el dispositivo ({admin.username})",
    ))

    # Keep the latest snapshot coherent for clients that reload before the next
    # telemetry frame. History rows are not modified.
    column = {
        "fan_1": "fan_1_state",
        "fan_2": "fan_2_state",
        "humidifier_1": "humidifier_1_state",
        "pump": "pump_state",
    }.get(actuator)
    if column:
        latest_result = await db.execute(
            select(Reading).order_by(desc(Reading.timestamp)).limit(1)
        )
        latest = latest_result.scalar_one_or_none()
        if latest is not None:
            setattr(latest, column, confirmed_state)

    await db.commit()

    # Every connected admin and public visitor updates without waiting for the
    # next sensor frame.
    await broadcast_actuator_state(actuator, confirmed_state, source="manual")

    return {**ack, "state": confirmed_state, "confirmed_at": confirmed_at}
