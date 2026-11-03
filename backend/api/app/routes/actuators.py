from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictBool
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.dependencies import get_admin_user
from app.models import ActiveConfig
from app.mqtt_commands import send_command, CommandTimeout, CommandUnavailable, CommandRejected

router = APIRouter(prefix="/api/actuators", tags=["actuators"])
ActuatorName = Literal["fan_1", "fan_2", "humidifier_1", "humidifier_2", "pump"]


class ActuatorCommand(BaseModel):
    state: StrictBool


@router.post("/{actuator}/command")
async def command_actuator(actuator: ActuatorName, command: ActuatorCommand,
                           db: AsyncSession = Depends(get_db),
                           admin=Depends(get_admin_user)):
    # OFF must always remain available, even with irrigation disabled.
    if actuator == "pump" and command.state:
        result = await db.execute(select(ActiveConfig).where(
            ActiveConfig.is_active == True).order_by(desc(ActiveConfig.version)).limit(1))
        config = result.scalar_one_or_none()
        if not config or not config.config_json.get("irrigation", {}).get("enabled", False):
            raise HTTPException(409, "Habilite el riego antes de encender la bomba")
    try:
        ack = await run_in_threadpool(send_command, actuator, command.state)
    except CommandRejected as exc:
        raise HTTPException(409, str(exc)) from exc
    except CommandUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except CommandTimeout as exc:
        raise HTTPException(504, str(exc)) from exc
    return {**ack, "confirmed_at": datetime.now(timezone.utc).isoformat()}
