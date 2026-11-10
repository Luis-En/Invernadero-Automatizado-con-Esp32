from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import log_action
from app.config import settings
from app.database import get_db
from app.dependencies import get_admin_user
from app.rate_limit import limiter
from app.routes.crops import (
    create_crop,
    create_crop_params,
    delete_crop,
    update_crop,
    update_crop_params,
)
from app.schemas import (
    CropCreate,
    CropParamCreate,
    CropParamUpdate,
    CropResponse,
    CropUpdate,
)

router = APIRouter(prefix="/crops", tags=["admin-crops"])


@router.post("", response_model=CropResponse, status_code=201)
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def admin_create_crop(
    payload: CropCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    crop = await create_crop(payload, db, admin)
    await log_action(
        db,
        "crop.create",
        f"crop:{crop.id}",
        user=admin,
        request=request,
        details={"name": crop.name},
    )
    return crop


@router.put("/{crop_id}", response_model=CropResponse)
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def admin_update_crop(
    crop_id: int,
    payload: CropUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    crop = await update_crop(crop_id, payload, db, admin)
    await log_action(
        db,
        "crop.update",
        f"crop:{crop_id}",
        user=admin,
        request=request,
        details={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return crop


@router.delete("/{crop_id}", status_code=204)
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def admin_delete_crop(
    crop_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    await delete_crop(crop_id, db, admin)
    await log_action(
        db,
        "crop.delete",
        f"crop:{crop_id}",
        user=admin,
        request=request,
    )
    return Response(status_code=204)


@router.post("/{crop_id}/params", status_code=201)
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def admin_create_crop_params(
    crop_id: int,
    payload: CropParamCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    params = await create_crop_params(crop_id, payload, db, admin)
    await log_action(
        db,
        "crop.params.create",
        f"crop:{crop_id}",
        user=admin,
        request=request,
    )
    return params


@router.put("/{crop_id}/params")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def admin_update_crop_params(
    crop_id: int,
    payload: CropParamUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user),
):
    params = await update_crop_params(crop_id, payload, db, admin)
    await log_action(
        db,
        "crop.params.update",
        f"crop:{crop_id}",
        user=admin,
        request=request,
        details={"fields": list(payload.model_dump(exclude_unset=True).keys())},
    )
    return params
