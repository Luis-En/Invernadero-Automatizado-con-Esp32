from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import log_action
from app.config import settings
from app.database import get_db
from app.dependencies import get_admin_user
from app.rate_limit import limiter
from app.routes.config import perform_apply_config
from app.schemas import ActiveConfigCreate, ActiveConfigResponse

router = APIRouter(prefix="/config", tags=["admin-config"])


@router.post("", response_model=ActiveConfigResponse)
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def admin_apply_config(
    payload: ActiveConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    config = await perform_apply_config(payload, db, admin)
    await log_action(
        db,
        "config.apply",
        f"config:v{config.version}",
        user=admin,
        request=request,
        details={"crop_id": config.crop_id},
    )
    return config
