import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from app.database import get_db
from app.models import ActiveConfig, ConfigHistory, Crop, Reading, Device, Photo, Event
from app.schemas import ActiveConfigCreate, ActiveConfigUpdate, ActiveConfigResponse, ConfigHistoryResponse, TelemetrySnapshot, SystemStatus
from app.dependencies import get_current_active_user, get_admin_user, get_optional_user

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


@router.get("/active", response_model=ActiveConfigResponse)
async def get_active_config(db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(
        select(ActiveConfig).where(ActiveConfig.is_active == True).order_by(desc(ActiveConfig.version)).limit(1)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="No active configuration")
    return config


@router.get("/history", response_model=List[ConfigHistoryResponse])
async def get_config_history(limit: int = 50, db: AsyncSession = Depends(get_db), user=Depends(get_current_active_user)):
    result = await db.execute(select(ConfigHistory).order_by(desc(ConfigHistory.created_at)).limit(limit))
    return result.scalars().all()


@router.post("/apply", response_model=ActiveConfigResponse)
async def apply_config(
    config_data: ActiveConfigCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user)
):
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
        config_json=config_data.config_json,
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
async def update_active_config(
    config_data: ActiveConfigUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_admin_user)
):
    result = await db.execute(
        select(ActiveConfig).where(ActiveConfig.is_active == True).order_by(desc(ActiveConfig.version)).limit(1)
    )
    current = result.scalar_one_or_none()
    if not current:
        raise HTTPException(status_code=404, detail="No active configuration")

    new_config_json = config_data.config_json if config_data.config_json is not None else current.config_json
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
async def confirm_config_received(version: int, db: AsyncSession = Depends(get_db)):
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
async def get_latest_telemetry(db: AsyncSession = Depends(get_db), user=Depends(get_optional_user)):
    result = await db.execute(select(Reading).order_by(desc(Reading.timestamp)).limit(1))
    reading = result.scalar_one_or_none()

    if not reading:
        return TelemetrySnapshot(
            timestamp=datetime.utcnow(),
            last_update=datetime.utcnow()
        )

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

    device_result = await db.execute(select(Device).where(Device.device_type == "field"))
    field_device = device_result.scalar_one_or_none()

    return TelemetrySnapshot(
        timestamp=reading.timestamp,
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
        last_update=reading.timestamp,
    )


@router.get("/telemetry/history")
async def get_telemetry_history(
    hours: int = 24,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_optional_user)
):
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(Reading).where(Reading.timestamp >= since).order_by(Reading.timestamp).limit(limit)
    )
    readings = result.scalars().all()

    return [
        {
            "timestamp": r.timestamp.isoformat(),
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
async def get_system_status(db: AsyncSession = Depends(get_db), user=Depends(get_optional_user)):
    from datetime import timedelta

    now = datetime.utcnow()
    threshold = now - timedelta(minutes=5)

    device_result = await db.execute(select(Device).where(Device.device_type.in_(["field", "gateway", "camera"])))
    devices = device_result.scalars().all()

    field_online = any(d.device_type == "field" and d.is_online and d.last_seen and d.last_seen > threshold for d in devices)
    gateway_online = any(d.device_type == "gateway" and d.is_online and d.last_seen and d.last_seen > threshold for d in devices)
    camera_online = any(d.device_type == "camera" and d.is_online and d.last_seen and d.last_seen > threshold for d in devices)

    telemetry_result = await db.execute(select(Reading).order_by(desc(Reading.timestamp)).limit(1))
    last_reading = telemetry_result.scalar_one_or_none()

    photo_result = await db.execute(select(Photo).order_by(desc(Photo.timestamp)).limit(1))
    last_photo = photo_result.scalar_one_or_none()

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

    return SystemStatus(
        field_esp32_online=field_online,
        gateway_esp32_online=gateway_online,
        camera_online=camera_online,
        last_telemetry=last_reading.timestamp if last_reading else None,
        last_photo=last_photo.timestamp if last_photo else None,
        active_config_version=active_config.version if active_config else None,
        active_crop=crop_name,
        irrigation_enabled=irrigation_enabled,
        alerts_count=len(alerts),
    )


@router.post("/telemetry", status_code=201)
async def receive_telemetry(
    payload: dict,
    db: AsyncSession = Depends(get_db)
):
    """Receive telemetry from serial bridge (no auth required for device)"""
    try:
        reading = Reading(
            timestamp=datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00")),
            temperature=payload.get("temperature"),
            humidity=payload.get("humidity"),
            pressure=payload.get("pressure"),
            soil_adc_a1=payload["soil_adc"][0],
            soil_adc_a2=payload["soil_adc"][1],
            soil_adc_a3=payload["soil_adc"][2],
            soil_adc_b1=payload["soil_adc"][3],
            soil_adc_b2=payload["soil_adc"][4],
            soil_adc_b3=payload["soil_adc"][5],
            soil_pct_a1=payload["soil_pct"][0],
            soil_pct_a2=payload["soil_pct"][1],
            soil_pct_a3=payload["soil_pct"][2],
            soil_pct_b1=payload["soil_pct"][3],
            soil_pct_b2=payload["soil_pct"][4],
            soil_pct_b3=payload["soil_pct"][5],
            soil_ok_a1=payload["soil_ok"][0],
            soil_ok_a2=payload["soil_ok"][1],
            soil_ok_a3=payload["soil_ok"][2],
            soil_ok_b1=payload["soil_ok"][3],
            soil_ok_b2=payload["soil_ok"][4],
            soil_ok_b3=payload["soil_ok"][5],
            fan_1_state=payload.get("fan_1_state", False),
            fan_2_state=payload.get("fan_2_state", False),
            humidifier_1_state=payload.get("humidifier_1_state", False),
            humidifier_2_state=payload.get("humidifier_2_state", False),
            pump_state=payload.get("pump_state", False),
            rssi=payload.get("rssi"),
            device_id=payload.get("device_id"),
            sequence=payload.get("sequence"),
        )
        db.add(reading)

        # Update device last_seen
        result = await db.execute(
            select(Device).where(Device.device_id == payload.get("device_id"))
        )
        device = result.scalar_one_or_none()
        if device:
            device.last_seen = reading.timestamp
            device.is_online = True
            device.rssi = payload.get("rssi")
        else:
            device = Device(
                device_id=payload.get("device_id", "field_esp32"),
                device_type="field",
                name="ESP32 Campo",
                last_seen=reading.timestamp,
                is_online=True,
                rssi=payload.get("rssi"),
            )
            db.add(device)

        await db.commit()

        # Broadcast to WebSocket clients
        await manager.broadcast({"type": "telemetry", "data": payload})

        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)