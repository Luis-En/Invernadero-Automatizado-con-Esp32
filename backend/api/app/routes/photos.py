import os
import binascii
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from app.database import get_db
from app.models import Photo
from app.schemas import PhotoResponse
from app.dependencies import get_current_active_user, get_admin_user, get_optional_user
from app.config import settings

router = APIRouter(prefix="/api/photos", tags=["photos"])

PHOTO_DIR = Path(settings.photo_storage_absolute)
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SUFFIX = ".chunk"


def photo_dir_for(ts: datetime) -> Path:
    d = PHOTO_DIR / ts.strftime("%Y/%m/%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


def compute_crc16(data: bytes) -> int:
    return binascii.crc_hqx(data, 0) & 0xFFFF

@router.get("", response_model=List[PhotoResponse])
async def list_photos(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_active_user),
):
    result = await db.execute(
        select(Photo).order_by(desc(Photo.timestamp)).limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.get("/latest", response_model=PhotoResponse)
async def get_latest_photo(db: AsyncSession = Depends(get_db), user=Depends(get_optional_user)):
    result = await db.execute(
        select(Photo).where(Photo.is_complete == True).order_by(desc(Photo.timestamp)).limit(1)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="No photos available")
    return photo


@router.get("/latest/file")
async def get_latest_photo_file(db: AsyncSession = Depends(get_db), user=Depends(get_optional_user)):
    result = await db.execute(
        select(Photo).where(Photo.is_complete == True).order_by(desc(Photo.timestamp)).limit(1)
    )
    photo = result.scalar_one_or_none()
    if not photo or not os.path.exists(photo.path):
        raise HTTPException(status_code=404, detail="No photos available")
    return FileResponse(photo.path, media_type="image/jpeg")


@router.post("/cleanup", status_code=200)
async def cleanup_old_photos(db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    cutoff = datetime.utcnow() - timedelta(days=settings.PHOTO_RETENTION_DAYS)
    result = await db.execute(select(Photo).where(Photo.timestamp < cutoff))
    old_photos = result.scalars().all()

    deleted = 0
    freed_bytes = 0
    for photo in old_photos:
        if os.path.exists(photo.path):
            freed_bytes += photo.size_bytes or 0
            os.remove(photo.path)
        for leftover in PHOTO_DIR.rglob(f"*_{photo.id}_*{CHUNK_SUFFIX}"):
            leftover.unlink(missing_ok=True)
        await db.delete(photo)
        deleted += 1

    await db.commit()
    return {"deleted": deleted, "freed_bytes": freed_bytes}


@router.post("/chunk", response_model=PhotoResponse)
async def receive_photo_chunk(
    chunk_data: bytes = File(...),
    sequence: int = Query(...),
    total_chunks: int = Query(..., ge=1),
    chunk_index: int = Query(..., ge=0),
    crc16: int = Query(...),
    device_id: str = Query("camera"),
    db: AsyncSession = Depends(get_db),
):
    if chunk_index >= total_chunks:
        raise HTTPException(status_code=400, detail="chunk_index out of range")
    if crc16 != compute_crc16(chunk_data):
        raise HTTPException(status_code=400, detail="CRC mismatch")

    now = datetime.utcnow()
    photo_dir = photo_dir_for(now)

    result = await db.execute(
        select(Photo).where(Photo.sequence == sequence).order_by(desc(Photo.timestamp)).limit(1)
    )
    photo = result.scalar_one_or_none()

    if not photo:
        target = photo_dir / f"{now.strftime('%H%M%S')}_{sequence}.jpg"
        photo = Photo(
            timestamp=now,
            path=str(target),
            filename=target.name,
            size_bytes=0,
            sequence=sequence,
            chunks_total=total_chunks,
            chunks_received=0,
            is_complete=False,
            device_id=device_id,
        )
        db.add(photo)
        await db.flush()

    chunk_path = photo_dir / f"{photo.id}_{chunk_index}{CHUNK_SUFFIX}"
    with open(chunk_path, "wb") as f:
        f.write(chunk_data)

    if photo.chunks_total != total_chunks:
        photo.chunks_total = max(photo.chunks_total or 0, total_chunks)

    photo.size_bytes = (photo.size_bytes or 0) + len(chunk_data)
    photo.chunks_received = (photo.chunks_received or 0) + 1
    photo.is_complete = photo.chunks_received >= photo.chunks_total

    await db.commit()
    await db.refresh(photo)

    if photo.is_complete:
        await reassemble_photo(photo, photo_dir, db)

    return photo


async def reassemble_photo(photo: Photo, photo_dir: Path, db: AsyncSession):
    if not photo.chunks_total:
        return

    chunks = []
    for i in range(photo.chunks_total):
        chunk_path = photo_dir / f"{photo.id}_{i}{CHUNK_SUFFIX}"
        if not chunk_path.exists():
            photo.is_complete = False
            await db.commit()
            return
        with open(chunk_path, "rb") as f:
            chunks.append(f.read())

    with open(photo.path, "wb") as f:
        for chunk in chunks:
            f.write(chunk)

    for i in range(photo.chunks_total):
        (photo_dir / f"{photo.id}_{i}{CHUNK_SUFFIX}").unlink(missing_ok=True)

    photo.size_bytes = os.path.getsize(photo.path)
    photo.is_complete = True

    try:
        from PIL import Image
        with Image.open(photo.path) as img:
            photo.width, photo.height = img.size
    except Exception:
        pass

    await db.commit()


@router.get("/{photo_id}", response_model=PhotoResponse)
async def get_photo(photo_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo


@router.get("/{photo_id}/file")
async def get_photo_file(photo_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    if not os.path.exists(photo.path):
        raise HTTPException(status_code=404, detail="Photo file not found on disk")
    return FileResponse(photo.path, media_type="image/jpeg")
