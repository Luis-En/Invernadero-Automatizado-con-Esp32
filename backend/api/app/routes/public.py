"""Unauthenticated read-only endpoints for the public dashboard.

Everything returned here is intentionally redacted: no device identifiers,
RSSI, sequence numbers, user data, notes, or configuration internals beyond
the irrigation threshold needed to explain the status.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.irrigation import assess_irrigation, thresholds_from_config
from app.models import ActiveConfig, Crop, Photo, Reading
from app.rate_limit import limiter
from app.routes.photos import _safe_photo_path
from app.schemas import (
    PublicCropParams,
    PublicCropResponse,
    PublicPhotoResponse,
    PublicSoilSensor,
    PublicTelemetry,
    WeatherOverview,
)
from app.weather import WeatherUnavailable, weather_service

router = APIRouter(prefix="/api/public", tags=["public"])

MAX_PUBLIC_WS_CONNECTIONS = 100


class PublicConnectionManager:
    def __init__(self, max_connections: int = MAX_PUBLIC_WS_CONNECTIONS):
        self.connections: List[WebSocket] = []
        self.max_connections = max_connections

    async def connect(self, websocket: WebSocket) -> bool:
        if len(self.connections) >= self.max_connections:
            await websocket.close(code=1013)
            return False
        await websocket.accept()
        self.connections.append(websocket)
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        for connection in list(self.connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


public_manager = PublicConnectionManager()


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _soil_sensors(soil_pct: List[Optional[float]], soil_ok: List[bool]) -> List[PublicSoilSensor]:
    ids = ["A1", "A2", "A3", "B1", "B2", "B3"]
    return [
        PublicSoilSensor(
            id=ids[index],
            pct=soil_pct[index] if index < len(soil_pct) else None,
            ok=bool(soil_ok[index]) if index < len(soil_ok) else False,
            row=ids[index][0],
        )
        for index in range(6)
    ]


def _averages(sensors: List[PublicSoilSensor]) -> Dict[str, Optional[float]]:
    valid_a = [s.pct for s in sensors if s.row == "A" and s.ok and s.pct is not None]
    valid_b = [s.pct for s in sensors if s.row == "B" and s.ok and s.pct is not None]
    valid_all = [s.pct for s in sensors if s.ok and s.pct is not None]
    return {
        "a": sum(valid_a) / len(valid_a) if valid_a else None,
        "b": sum(valid_b) / len(valid_b) if valid_b else None,
        "all": sum(valid_all) / len(valid_all) if valid_all else None,
    }


def _assemble_public(
    *,
    timestamp: datetime,
    temperature: Optional[float],
    humidity: Optional[float],
    pressure: Optional[float],
    soil_pct: List[Optional[float]],
    soil_ok: List[bool],
    actuators: Dict[str, bool],
    config_json: Optional[dict],
    crop_name: Optional[str],
) -> PublicTelemetry:
    sensors = _soil_sensors(soil_pct, soil_ok)
    averages = _averages(sensors)
    on_below, off_above = thresholds_from_config(config_json)
    assessment = assess_irrigation(
        [sensor.pct for sensor in sensors],
        [sensor.ok for sensor in sensors],
        config_json,
        previously_needed=False,
    )
    stale = (datetime.utcnow() - timestamp) > timedelta(
        minutes=settings.IRRIGATION_MAX_AGE_MIN
    )
    irrigation_enabled = bool(
        (config_json or {}).get("irrigation", {}).get("enabled", False)
    )
    return PublicTelemetry(
        timestamp=_as_utc(timestamp),
        last_update=_as_utc(timestamp),
        temperature=temperature,
        humidity=humidity,
        pressure=pressure,
        soil_sensors=sensors,
        soil_avg_row_a=averages["a"],
        soil_avg_row_b=averages["b"],
        soil_avg_general=averages["all"],
        actuators=actuators,
        irrigation_enabled=irrigation_enabled,
        irrigation_needed=assessment.needed and not stale,
        soil_threshold_pct=on_below,
        soil_off_above_pct=off_above,
        active_crop=crop_name,
        telemetry_stale=stale,
    )


def build_public_telemetry(reading: Optional[Reading], config_json: Optional[dict], crop_name: Optional[str]) -> PublicTelemetry:
    now = datetime.utcnow()
    if reading is None:
        on_below, off_above = thresholds_from_config(config_json)
        return PublicTelemetry(
            timestamp=now,
            last_update=now,
            irrigation_needed=False,
            soil_threshold_pct=on_below,
            soil_off_above_pct=off_above,
            active_crop=crop_name,
        )
    return _assemble_public(
        timestamp=reading.timestamp,
        temperature=reading.temperature,
        humidity=reading.humidity,
        pressure=reading.pressure,
        soil_pct=[
            reading.soil_pct_a1,
            reading.soil_pct_a2,
            reading.soil_pct_a3,
            reading.soil_pct_b1,
            reading.soil_pct_b2,
            reading.soil_pct_b3,
        ],
        soil_ok=[
            bool(reading.soil_ok_a1),
            bool(reading.soil_ok_a2),
            bool(reading.soil_ok_a3),
            bool(reading.soil_ok_b1),
            bool(reading.soil_ok_b2),
            bool(reading.soil_ok_b3),
        ],
        actuators={
            "fan_1": bool(reading.fan_1_state),
            "fan_2": bool(reading.fan_2_state),
            "humidifier_1": bool(reading.humidifier_1_state),
            "humidifier_2": bool(reading.humidifier_2_state),
            "pump": bool(reading.pump_state),
        },
        config_json=config_json,
        crop_name=crop_name,
    )


def build_public_telemetry_from_payload(payload, config_json: Optional[dict], crop_name: Optional[str]) -> PublicTelemetry:
    return _assemble_public(
        timestamp=payload.timestamp.astimezone(timezone.utc).replace(tzinfo=None),
        temperature=payload.temperature,
        humidity=payload.humidity,
        pressure=payload.pressure,
        soil_pct=list(payload.soil_pct),
        soil_ok=list(payload.soil_ok),
        actuators={
            "fan_1": payload.fan_1_state,
            "fan_2": payload.fan_2_state,
            "humidifier_1": payload.humidifier_1_state,
            "humidifier_2": payload.humidifier_2_state,
            "pump": payload.pump_state,
        },
        config_json=config_json,
        crop_name=crop_name,
    )


async def _active_config_and_crop(
    db: AsyncSession,
) -> tuple[Optional[dict], Optional[str]]:
    result = await db.execute(
        select(ActiveConfig)
        .where(ActiveConfig.is_active == True)  # noqa: E712
        .order_by(desc(ActiveConfig.version))
        .limit(1)
    )
    active_config = result.scalar_one_or_none()
    config_json = active_config.config_json if active_config else None
    crop_name = None
    if active_config and active_config.crop_id:
        crop_result = await db.execute(select(Crop).where(Crop.id == active_config.crop_id))
        crop = crop_result.scalar_one_or_none()
        crop_name = crop.display_name if crop else None
    return config_json, crop_name


@router.get("/telemetry", response_model=PublicTelemetry)
@limiter.limit("60/minute")
async def public_telemetry(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reading).order_by(desc(Reading.timestamp)).limit(1))
    reading = result.scalar_one_or_none()
    config_json, crop_name = await _active_config_and_crop(db)
    return build_public_telemetry(reading, config_json, crop_name)


@router.get("/telemetry/history")
@limiter.limit("30/minute")
async def public_telemetry_history(
    request: Request,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(1000, ge=1, le=3000),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(Reading)
        .where(Reading.timestamp >= since)
        .order_by(Reading.timestamp)
        .limit(limit)
    )
    return [
        {
            "timestamp": _as_utc(row.timestamp).isoformat(),
            "temperature": row.temperature,
            "humidity": row.humidity,
            "pressure": row.pressure,
            "soil_a1": row.soil_pct_a1,
            "soil_a2": row.soil_pct_a2,
            "soil_a3": row.soil_pct_a3,
            "soil_b1": row.soil_pct_b1,
            "soil_b2": row.soil_pct_b2,
            "soil_b3": row.soil_pct_b3,
        }
        for row in result.scalars().all()
    ]


@router.get("/photos", response_model=List[PublicPhotoResponse])
@limiter.limit("60/minute")
async def public_photos(
    request: Request,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Photo)
        .where(Photo.is_complete == True)  # noqa: E712
        .order_by(desc(Photo.timestamp))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/photos/latest", response_model=PublicPhotoResponse)
@limiter.limit("60/minute")
async def public_latest_photo(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Photo).where(Photo.is_complete == True).order_by(desc(Photo.timestamp)).limit(1)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="No photos available")
    return photo


@router.get("/photos/latest/file")
async def public_latest_photo_file(db: AsyncSession = Depends(get_db)):
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


@router.get("/photos/{photo_id}/file")
async def public_photo_file(photo_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()
    if not photo or not photo.is_complete:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = _safe_photo_path(photo.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/weather", response_model=WeatherOverview)
@limiter.limit("30/minute")
async def public_weather(
    request: Request,
    hours: int = Query(48, ge=6, le=120),
):
    try:
        return await weather_service.get_overview(hours=hours)
    except WeatherUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/crops", response_model=List[PublicCropResponse])
@limiter.limit("30/minute")
async def public_crops(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Crop)
        .options(selectinload(Crop.params))
        .where(Crop.is_active == True)  # noqa: E712
        .order_by(Crop.name)
    )
    crops = result.scalars().all()
    response = []
    for crop in crops:
        params = crop.params
        response.append(
            PublicCropResponse(
                id=crop.id,
                name=crop.name,
                display_name=crop.display_name,
                description=crop.description,
                params=PublicCropParams(**params.__dict__) if params else None,
            )
        )
    return response


def _origin_allowed(origin: Optional[str], host: str) -> bool:
    if not origin:
        return True
    allowed = set(settings.cors_origins_list)
    if host:
        allowed.add(f"http://{host}")
        allowed.add(f"https://{host}")
    parsed = urlparse(origin)
    return bool(parsed.scheme and parsed.netloc) and origin in allowed


@router.websocket("/ws")
async def public_websocket(websocket: WebSocket):
    if not _origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host", "")):
        await websocket.close(code=1008)
        return
    if not await public_manager.connect(websocket):
        return
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        public_manager.disconnect(websocket)
    except Exception:
        public_manager.disconnect(websocket)
