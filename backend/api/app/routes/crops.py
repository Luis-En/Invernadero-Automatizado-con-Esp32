from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from app.database import get_db
from app.models import Crop, CropParam
from app.schemas import CropCreate, CropUpdate, CropResponse, CropWithParamsResponse, CropParamCreate, CropParamUpdate, CropParamResponse
from app.dependencies import get_current_active_user, get_admin_user

router = APIRouter(prefix="/api/crops", tags=["crops"])


@router.get("", response_model=List[CropResponse])
async def list_crops(db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(select(Crop).where(Crop.is_active == True).order_by(Crop.name))
    return result.scalars().all()


@router.get("/all", response_model=List[CropResponse])
async def list_all_crops(db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(Crop).order_by(Crop.name))
    return result.scalars().all()


@router.get("/{crop_id}", response_model=CropWithParamsResponse)
async def get_crop(crop_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(
        select(Crop).options(selectinload(Crop.params)).where(Crop.id == crop_id)
    )
    crop = result.scalar_one_or_none()
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")
    return crop


@router.post("", response_model=CropResponse, status_code=201)
async def create_crop(crop_data: CropCreate, db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(Crop).where(Crop.name == crop_data.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Crop name already exists")
    crop = Crop(**crop_data.model_dump())
    db.add(crop)
    await db.commit()
    await db.refresh(crop)
    return crop


@router.put("/{crop_id}", response_model=CropResponse)
async def update_crop(crop_id: int, crop_data: CropUpdate, db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(Crop).where(Crop.id == crop_id))
    crop = result.scalar_one_or_none()
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")
    for field, value in crop_data.model_dump(exclude_unset=True).items():
        setattr(crop, field, value)
    await db.commit()
    await db.refresh(crop)
    return crop


@router.delete("/{crop_id}", status_code=204)
async def delete_crop(crop_id: int, db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(Crop).where(Crop.id == crop_id))
    crop = result.scalar_one_or_none()
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")
    crop.is_active = False
    await db.commit()


@router.get("/{crop_id}/params", response_model=CropParamResponse)
async def get_crop_params(crop_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(select(CropParam).where(CropParam.crop_id == crop_id))
    params = result.scalar_one_or_none()
    if not params:
        raise HTTPException(status_code=404, detail="Crop parameters not found")
    return params


@router.post("/{crop_id}/params", response_model=CropParamResponse, status_code=201)
async def create_crop_params(crop_id: int, params_data: CropParamCreate, db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(Crop).where(Crop.id == crop_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Crop not found")

    result = await db.execute(select(CropParam).where(CropParam.crop_id == crop_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Parameters already exist for this crop")

    params = CropParam(**params_data.model_dump())
    db.add(params)
    await db.commit()
    await db.refresh(params)
    return params


@router.put("/{crop_id}/params", response_model=CropParamResponse)
async def update_crop_params(crop_id: int, params_data: CropParamUpdate, db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    result = await db.execute(select(CropParam).where(CropParam.crop_id == crop_id))
    params = result.scalar_one_or_none()
    if not params:
        raise HTTPException(status_code=404, detail="Crop parameters not found")
    for field, value in params_data.model_dump(exclude_unset=True).items():
        setattr(params, field, value)
    await db.commit()
    await db.refresh(params)
    return params