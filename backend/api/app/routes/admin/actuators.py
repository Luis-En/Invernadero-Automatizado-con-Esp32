from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, StrictBool
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import log_action
from app.config import settings
from app.database import get_db
from app.dependencies import get_admin_user
from app.rate_limit import limiter
from app.routes.actuators import perform_actuator_command

router = APIRouter(prefix="/actuators", tags=["admin-actuators"])

ActuatorName = Literal["fan_1", "fan_2", "humidifier_1", "humidifier_2", "pump"]


class AdminActuatorCommand(BaseModel):
    actuator: ActuatorName
    state: StrictBool


@router.post("/control")
@limiter.limit(settings.RATE_LIMIT_ACTUATOR)
async def control_actuator(
    payload: AdminActuatorCommand,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    result = await perform_actuator_command(payload.actuator, payload.state, db, admin)
    await log_action(
        db,
        "actuator.control",
        f"actuator:{payload.actuator}",
        user=admin,
        request=request,
        details={"state": payload.state},
    )
    return result
