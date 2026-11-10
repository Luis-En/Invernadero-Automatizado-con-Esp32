import os
import binascii
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Deque, Dict, List

from fastapi import APIRouter, Depends, HTTPException, File, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models import Photo
from app.rate_limit import limiter
from app.schemas import PhotoResponse
from app.dependencies import (
    get_current_active_user,
    get_admin_user,
    require_device_token,
)
from app.config import settings

router = APIRouter(prefix="/api/photos", tags=["photos"])

PHOTO_DIR = Path(settings.photo_storage_absolute)
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SUFFIX = ".chunk"


def _safe_photo_path(value: str) -> Path:
    """Resolve a stored path and refuse anything outside the photo root."""
    root = PHOTO_DIR.resolve()
    target = Path(value).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(status_code=404, detail="Photo file not found")
    return target

# Per-device sliding window used to stop a misbehaving camera from filling the
# disk. Only chunk uploads are counted; listing is authenticated.
_chunk_windows: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=2048))


def _check_chunk_rate(device_id: str) -> None:
    now = time.monotonic()
    window = _chunk_windows[device_id]
    while window and now - window[0] > 60.0:
        window.popleft()
    if len(window) >= settings.PHOTO_MAX_CHUNKS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Photo chunk rate limit exceeded")
    window.append(now)


def photo_dir_for(ts: datetime) -> Path:
    d = PHOTO_DIR / ts.strftime("%Y/%m/%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


def compute_crc16(data: bytes) -> int:
    return binascii.crc_hqx(data, 0) & 0xFFFF

@router.get("", response_model=List[PhotoResponse])
async def list_photos(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100000),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_active_user),
):
    result = await db.execute(
        select(Photo)
        .where(Photo.is_complete == True)
        .order_by(desc(Photo.timestamp))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/latest", response_model=PhotoResponse)
async def get_latest_photo(db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(
        select(Photo).where(Photo.is_complete == True).order_by(desc(Photo.timestamp)).limit(1)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="No photos available")
    return photo


@router.get("/latest/file")
async def get_latest_photo_file(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_active_user),
):
    """Serve the newest complete JPEG to an authenticated user.

    The static /photos mount was removed: the frontend fetches the bytes with
    its bearer token and renders them from an object URL.
    """
    result = await db.execute(
        select(Photo).where(Photo.is_complete == True).order_by(desc(Photo.timestamp)).limit(1)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="No photos available")
    path = _safe_photo_path(photo.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No photos available")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/cleanup", status_code=200)
async def cleanup_old_photos(db: AsyncSession = Depends(get_db), admin=Depends(get_admin_user)):
    cutoff = datetime.utcnow() - timedelta(days=settings.PHOTO_RETENTION_DAYS)
    result = await db.execute(select(Photo).where(Photo.timestamp < cutoff))
    old_photos = result.scalars().all()

    deleted = 0
    freed_bytes = 0
    for photo in old_photos:
        try:
            path = _safe_photo_path(photo.path)
            if path.exists():
                freed_bytes += photo.size_bytes or 0
                path.unlink()
        except HTTPException:
            pass
        for leftover in PHOTO_DIR.rglob(f"*_{photo.id}_*{CHUNK_SUFFIX}"):
            leftover.unlink(missing_ok=True)
        await db.delete(photo)
        deleted += 1

    await db.commit()
    return {"deleted": deleted, "freed_bytes": freed_bytes}


@router.post("/chunk", response_model=PhotoResponse)
@limiter.limit(settings.RATE_LIMIT_PHOTOS)
async def receive_photo_chunk(
    request: Request,
    chunk_data: bytes = File(...),
    sequence: int = Query(...),
    total_chunks: int = Query(..., ge=1),
    chunk_index: int = Query(..., ge=0),
    crc16: int = Query(...),
    device_id: str = Query("camera", max_length=50),
    db: AsyncSession = Depends(get_db),
    device=Depends(require_device_token),
):
    _check_chunk_rate(device_id)
    if chunk_index >= total_chunks:
        raise HTTPException(status_code=400, detail="chunk_index out of range")
    if total_chunks > settings.PHOTO_MAX_TOTAL_CHUNKS:
        raise HTTPException(status_code=413, detail="total_chunks exceeds the configured limit")
    if len(chunk_data) > settings.photo_max_bytes:
        raise HTTPException(status_code=413, detail="chunk exceeds PHOTO_MAX_SIZE_MB")
    if crc16 != compute_crc16(chunk_data):
        raise HTTPException(status_code=400, detail="CRC mismatch")

    now = datetime.utcnow()
    photo_dir = photo_dir_for(now)

    # The camera restarts its sequence counter at 0 on every boot, so the same
    # sequence can appear more than once. Only continue a photo that is still
    # incomplete and recent; otherwise start a fresh record so fragments from
    # an earlier photo are never mixed in.
    cutoff = now - timedelta(minutes=15)
    result = await db.execute(
        select(Photo)
        .where(
            Photo.sequence == sequence,
            Photo.device_id == device_id,
            Photo.is_complete.is_(False),
            Photo.timestamp >= cutoff,
        )
        .order_by(desc(Photo.timestamp))
        .limit(1)
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
    is_new_chunk = not chunk_path.exists()
    if is_new_chunk and (photo.size_bytes or 0) + len(chunk_data) > settings.photo_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"photo exceeds PHOTO_MAX_SIZE_MB ({settings.PHOTO_MAX_SIZE_MB} MB)",
        )
    with open(chunk_path, "wb") as f:
        f.write(chunk_data)

    if photo.chunks_total != total_chunks:
        photo.chunks_total = max(photo.chunks_total or 0, total_chunks)

    # Count each fragment once, even if the same one is delivered twice.
    if is_new_chunk:
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

    # Never keep/serve arbitrary bytes as an image. The camera must send JPEG.
    with open(photo.path, "rb") as f:
        header = f.read(3)
    if header[:3] != b"\xff\xd8\xff":
        Path(photo.path).unlink(missing_ok=True)
        photo.is_complete = False
        await db.commit()
        raise HTTPException(status_code=400, detail="La imagen no es un JPEG válido")

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
async def get_photo_file(
    photo_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_active_user),
):
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = _safe_photo_path(photo.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found on disk")
    return FileResponse(path, media_type="image/jpeg")
