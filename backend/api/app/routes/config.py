from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from app.database import get_db
from app.models import ActiveConfig, ConfigHistory, Crop, Reading, Device, Photo, Event
from app.irrigation import assess_irrigation, soil_from_reading
from app.config import settings
from app.rate_limit import limiter
from app.schemas import (
    ActiveConfigCreate,
    ActiveConfigUpdate,
    ActiveConfigResponse,
    ConfigHistoryResponse,
    TelemetrySnapshot,
    TelemetryPayload,
    SystemStatus,
)
from app.dependencies import (
    get_current_active_user,
    get_admin_user,
    require_device_token,
)

router = APIRouter(prefix="/api/config", tags=["config"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite stores naive datetimes; the API contract is UTC-aware."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@router.get("/active", response_model=ActiveConfigResponse)
async def get_active_config(db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(
        select(ActiveConfig).where(ActiveConfig.is_active == True).order_by(desc(ActiveConfig.version)).limit(1)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="No active configuration")
    return config


@router.get("/device/active", response_model=ActiveConfigResponse)
async def get_active_config_for_device(
    db: AsyncSession = Depends(get_db),
    device=Depends(require_device_token),
):
    """Active configuration for the serial bridge/gateway.

    Uses the shared device token instead of a human account so the bridge does
    not have to keep a viewer password.
    """
    result = await db.execute(
        select(ActiveConfig).where(ActiveConfig.is_active == True).order_by(desc(ActiveConfig.version)).limit(1)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="No active configuration")
    return config


@router.get("/history", response_model=List[ConfigHistoryResponse])
async def get_config_history(limit: int = Query(50, ge=1, le=500), db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(select(ConfigHistory).order_by(desc(ConfigHistory.created_at)).limit(limit))
    return result.scalars().all()


@router.post("/apply", response_model=ActiveConfigResponse)
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def apply_config(
    config_data: ActiveConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user)
):
    return await perform_apply_config(config_data, db, admin)


async def perform_apply_config(config_data: ActiveConfigCreate, db: AsyncSession, admin):
    current = await db.execute(
        select(ActiveConfig).where(ActiveConfig.is_active == True).order_by(desc(ActiveConfig.version)).limit(1)
    )
    current_config = current.scalar_one_or_none()
    new_version = (current_config.version + 1) if current_config else 1

    if current_config:
        current_config.is_active = False
        history = ConfigHistory(
            config_json=current_config.config_json,
            version=current_config.version,
            crop_id=current_config.crop_id,
            changed_by=admin.id,
            change_reason=f"Replaced by version {new_version}"
        )
        db.add(history)

    new_config = ActiveConfig(
        config_json=config_data.config_json.model_dump(),
        version=new_version,
        crop_id=config_data.crop_id,
        applied_by=admin.id,
        esp32_confirmed=False
    )
    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)

    await manager.broadcast({"type": "config_update", "data": ActiveConfigResponse.model_validate(new_config).model_dump()})
    return new_config


@router.put("/active", response_model=ActiveConfigResponse)
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def update_active_config(
    config_data: ActiveConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user)
):
    result = await db.execute(
        select(ActiveConfig).where(ActiveConfig.is_active == True).order_by(desc(ActiveConfig.version)).limit(1)
    )
    current = result.scalar_one_or_none()
    if not current:
        raise HTTPException(status_code=404, detail="No active configuration")

    new_config_json = (
        config_data.config_json.model_dump()
        if config_data.config_json is not None
        else current.config_json
    )
    new_crop_id = config_data.crop_id if config_data.crop_id is not None else current.crop_id

    current.is_active = False
    db.add(ConfigHistory(
        config_json=current.config_json,
        version=current.version,
        crop_id=current.crop_id,
        changed_by=admin.id,
        change_reason="Updated active config",
    ))

    new_config = ActiveConfig(
        config_json=new_config_json,
        version=current.version + 1,
        crop_id=new_crop_id,
        applied_by=admin.id,
        esp32_confirmed=False,
    )
    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)

    await manager.broadcast({"type": "config_update", "data": ActiveConfigResponse.model_validate(new_config).model_dump()})
    return new_config


@router.post("/confirm/{version}", response_model=ActiveConfigResponse)
async def confirm_config_received(
    version: int,
    db: AsyncSession = Depends(get_db),
    device=Depends(require_device_token),
):
    result = await db.execute(
        select(ActiveConfig).where(
            ActiveConfig.version == version,
            ActiveConfig.is_active == True,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Active configuration version not found")
    config.esp32_confirmed = True
    config.esp32_confirmed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(config)
    await manager.broadcast({"type": "config_confirmed", "version": version})
    return config


@router.get("/telemetry/latest", response_model=TelemetrySnapshot)
async def get_latest_telemetry(db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(select(Reading).order_by(desc(Reading.timestamp)).limit(1))
    reading = result.scalar_one_or_none()

    if not reading:
        now = datetime.now(timezone.utc)
        return TelemetrySnapshot(timestamp=now, last_update=now)

    soil_sensors = [
        {"id": "A1", "adc": reading.soil_adc_a1, "pct": reading.soil_pct_a1, "ok": reading.soil_ok_a1, "row": "A"},
        {"id": "A2", "adc": reading.soil_adc_a2, "pct": reading.soil_pct_a2, "ok": reading.soil_ok_a2, "row": "A"},
        {"id": "A3", "adc": reading.soil_adc_a3, "pct": reading.soil_pct_a3, "ok": reading.soil_ok_a3, "row": "A"},
        {"id": "B1", "adc": reading.soil_adc_b1, "pct": reading.soil_pct_b1, "ok": reading.soil_ok_b1, "row": "B"},
        {"id": "B2", "adc": reading.soil_adc_b2, "pct": reading.soil_pct_b2, "ok": reading.soil_ok_b2, "row": "B"},
        {"id": "B3", "adc": reading.soil_adc_b3, "pct": reading.soil_pct_b3, "ok": reading.soil_ok_b3, "row": "B"},
    ]

    valid_a = [s["pct"] for s in soil_sensors if s["row"] == "A" and s["ok"] and s["pct"] is not None]
    valid_b = [s["pct"] for s in soil_sensors if s["row"] == "B" and s["ok"] and s["pct"] is not None]
    valid_all = [s["pct"] for s in soil_sensors if s["ok"] and s["pct"] is not None]

    config_result = await db.execute(
        select(ActiveConfig).where(ActiveConfig.is_active == True).order_by(desc(ActiveConfig.version)).limit(1)
    )
    active_config = config_result.scalar_one_or_none()

    crop_name = None
    if active_config and active_config.crop_id:
        crop_result = await db.execute(select(Crop).where(Crop.id == active_config.crop_id))
        crop = crop_result.scalar_one_or_none()
        if crop:
            crop_name = crop.display_name

    return TelemetrySnapshot(
        timestamp=_as_utc(reading.timestamp),
        temperature=reading.temperature,
        humidity=reading.humidity,
        pressure=reading.pressure,
        soil_sensors=soil_sensors,
        soil_avg_row_a=sum(valid_a) / len(valid_a) if valid_a else None,
        soil_avg_row_b=sum(valid_b) / len(valid_b) if valid_b else None,
        soil_avg_general=sum(valid_all) / len(valid_all) if valid_all else None,
        actuators={
            "fan_1": reading.fan_1_state,
            "fan_2": reading.fan_2_state,
            "humidifier_1": reading.humidifier_1_state,
            "humidifier_2": reading.humidifier_2_state,
            "pump": reading.pump_state,
        },
        rssi=reading.rssi,
        device_id=reading.device_id,
        sequence=reading.sequence,
        last_update=_as_utc(reading.timestamp),
    )


@router.get("/telemetry/history")
async def get_telemetry_history(
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(1000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_active_user)
):
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(Reading).where(Reading.timestamp >= since).order_by(Reading.timestamp).limit(limit)
    )
    readings = result.scalars().all()

    return [
        {
            "timestamp": _as_utc(r.timestamp).isoformat(),
            "temperature": r.temperature,
            "humidity": r.humidity,
            "pressure": r.pressure,
            "soil_a1": r.soil_pct_a1, "soil_a2": r.soil_pct_a2, "soil_a3": r.soil_pct_a3,
            "soil_b1": r.soil_pct_b1, "soil_b2": r.soil_pct_b2, "soil_b3": r.soil_pct_b3,
            "fan_1": r.fan_1_state, "fan_2": r.fan_2_state,
            "humidifier_1": r.humidifier_1_state, "humidifier_2": r.humidifier_2_state,
            "pump": r.pump_state,
        }
        for r in readings
    ]


@router.get("/status", response_model=SystemStatus)
async def get_system_status(db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    from datetime import timedelta

    now = datetime.utcnow()

    telemetry_result = await db.execute(select(Reading).order_by(desc(Reading.timestamp)).limit(1))
    last_reading = telemetry_result.scalar_one_or_none()

    photo_result = await db.execute(select(Photo).order_by(desc(Photo.timestamp)).limit(1))
    last_photo = photo_result.scalar_one_or_none()

    # A reading only reaches the API through the gateway, so fresh telemetry
    # means both the field and the gateway are alive. Photos arrive every 3
    # minutes; allow 10 before declaring the camera offline.
    field_online = last_reading is not None and (now - last_reading.timestamp) <= timedelta(minutes=2)
    gateway_online = field_online
    camera_online = last_photo is not None and (now - last_photo.timestamp) <= timedelta(minutes=10)

    config_result = await db.execute(
        select(ActiveConfig).where(ActiveConfig.is_active == True).order_by(desc(ActiveConfig.version)).limit(1)
    )
    active_config = config_result.scalar_one_or_none()

    crop_name = None
    if active_config and active_config.crop_id:
        crop_result = await db.execute(select(Crop).where(Crop.id == active_config.crop_id))
        crop = crop_result.scalar_one_or_none()
        if crop:
            crop_name = crop.display_name

    alerts_result = await db.execute(
        select(Event).where(Event.acknowledged == False).order_by(desc(Event.timestamp))
    )
    alerts = alerts_result.scalars().all()

    irrigation_enabled = False
    if active_config:
        irrigation_enabled = active_config.config_json.get("irrigation", {}).get("enabled", False)

    assessment = None
    telemetry_stale = False
    if last_reading is not None:
        telemetry_stale = (now - last_reading.timestamp) > timedelta(
            minutes=settings.IRRIGATION_MAX_AGE_MIN
        )
        soil_values, soil_flags = soil_from_reading(last_reading)
        assessment = assess_irrigation(
            soil_values,
            soil_flags,
            active_config.config_json if active_config else None,
            previously_needed=False,
        )

    return SystemStatus(
        field_esp32_online=field_online,
        gateway_esp32_online=gateway_online,
        camera_online=camera_online,
        last_telemetry=_as_utc(last_reading.timestamp) if last_reading else None,
        last_photo=_as_utc(last_photo.timestamp) if last_photo else None,
        active_config_version=active_config.version if active_config else None,
        active_crop=crop_name,
        irrigation_enabled=irrigation_enabled,
        alerts_count=len(alerts),
        soil_avg_pct=assessment.soil_avg if assessment else None,
        soil_threshold_pct=assessment.on_below if assessment else None,
        soil_off_above_pct=assessment.off_above if assessment else None,
        irrigation_needed=(assessment.needed if assessment else False) and not telemetry_stale,
        valid_soil_sensors=assessment.valid_sensors if assessment else 0,
        telemetry_stale=telemetry_stale,
    )


@router.post("/telemetry", status_code=201)
async def receive_telemetry(
    payload: TelemetryPayload,
    db: AsyncSession = Depends(get_db),
    device=Depends(require_device_token),
):
    """Receive validated telemetry from the serial bridge (device token)."""
    stored_timestamp = payload.timestamp.astimezone(timezone.utc).replace(tzinfo=None)
    reading = Reading(
        timestamp=stored_timestamp,
        temperature=payload.temperature,
        humidity=payload.humidity,
        pressure=payload.pressure,
        soil_adc_a1=payload.soil_adc[0],
        soil_adc_a2=payload.soil_adc[1],
        soil_adc_a3=payload.soil_adc[2],
        soil_adc_b1=payload.soil_adc[3],
        soil_adc_b2=payload.soil_adc[4],
        soil_adc_b3=payload.soil_adc[5],
        soil_pct_a1=payload.soil_pct[0],
        soil_pct_a2=payload.soil_pct[1],
        soil_pct_a3=payload.soil_pct[2],
        soil_pct_b1=payload.soil_pct[3],
        soil_pct_b2=payload.soil_pct[4],
        soil_pct_b3=payload.soil_pct[5],
        soil_ok_a1=payload.soil_ok[0],
        soil_ok_a2=payload.soil_ok[1],
        soil_ok_a3=payload.soil_ok[2],
        soil_ok_b1=payload.soil_ok[3],
        soil_ok_b2=payload.soil_ok[4],
        soil_ok_b3=payload.soil_ok[5],
        fan_1_state=payload.fan_1_state,
        fan_2_state=payload.fan_2_state,
        humidifier_1_state=payload.humidifier_1_state,
        humidifier_2_state=payload.humidifier_2_state,
        pump_state=payload.pump_state,
        rssi=payload.rssi,
        device_id=payload.device_id,
        sequence=payload.sequence,
    )
    db.add(reading)

    # Update device last_seen. A device_id can have older duplicate rows
    # from previous runs, so take the most recent one instead of assuming
    # exactly one match.
    result = await db.execute(
        select(Device)
        .where(Device.device_id == payload.device_id)
        .order_by(desc(Device.last_seen))
        .limit(1)
    )
    device_row = result.scalars().first()
    if device_row:
        device_row.last_seen = stored_timestamp
        device_row.is_online = True
        device_row.rssi = payload.rssi
    else:
        device_row = Device(
            device_id=payload.device_id or "field_esp32",
            device_type="field",
            name="ESP32 Campo",
            last_seen=stored_timestamp,
            is_online=True,
            rssi=payload.rssi,
        )
        db.add(device_row)

    await db.commit()

    broadcast_payload = payload.model_dump(mode="json")
    await manager.broadcast({"type": "telemetry", "data": broadcast_payload})

    # Public stream: redacted subset, no device identifiers or RSSI.
    try:
        from app.routes.public import build_public_telemetry_from_payload, public_manager

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
        public_data = build_public_telemetry_from_payload(
            payload, config_json, crop_name
        ).model_dump(mode="json")
        await public_manager.broadcast({"type": "telemetry", "data": public_data})
    except Exception:
        pass

    return {"status": "ok"}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Browsers authenticate the WebSocket handshake with the HttpOnly session
    # cookie. Non-browser clients may use an Authorization: Bearer header.
    # Query-string tokens are intentionally no longer accepted because URLs
    # are commonly written to access logs.
    from app.auth import decode_access_token
    from app.config import settings
    import secrets

    auth_token = websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    if not auth_token:
        authorization = websocket.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            auth_token = authorization[7:].strip()

    configured = (settings.DEVICE_API_TOKEN or "").strip()
    device_ok = bool(configured and auth_token) and secrets.compare_digest(
        auth_token, configured
    )
    user_ok = decode_access_token(auth_token) is not None if auth_token else False

    # Defence in depth against Cross-Site WebSocket Hijacking.
    origin = websocket.headers.get("origin")
    if origin:
        host = websocket.headers.get("host", "")
        allowed = set(settings.cors_origins_list)
        if host:
            allowed.add(f"http://{host}")
            allowed.add(f"https://{host}")
        if origin not in allowed:
            await websocket.close(code=1008)
            return

    if not (device_ok or user_ok):
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)