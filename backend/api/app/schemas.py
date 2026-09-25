from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class UserRole(str, Enum):
    VIEWER = "viewer"
    ADMIN = "admin"


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    role: UserRole = UserRole.VIEWER


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class UserUpdate(BaseModel):
    email: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserInDB(UserBase):
    id: int
    hashed_password: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[UserRole] = None


class CropBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    display_name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None


class CropCreate(CropBase):
    pass


class CropUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CropResponse(CropBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CropParamBase(BaseModel):
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    temp_night_min: Optional[float] = None
    temp_night_max: Optional[float] = None
    humidity_min: Optional[float] = None
    humidity_max: Optional[float] = None
    soil_moisture_min_pct: Optional[int] = Field(None, ge=0, le=100)
    soil_moisture_max_pct: Optional[int] = Field(None, ge=0, le=100)
    hysteresis_temp_on: Optional[float] = None
    hysteresis_temp_off: Optional[float] = None
    hysteresis_humidity_on: Optional[float] = None
    hysteresis_humidity_off: Optional[float] = None
    hysteresis_soil_on: Optional[int] = Field(None, ge=0, le=100)
    hysteresis_soil_off: Optional[int] = Field(None, ge=0, le=100)
    source_reference: Optional[str] = Field(None, max_length=255)
    source_url: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None


class CropParamCreate(CropParamBase):
    crop_id: int


class CropParamUpdate(CropParamBase):
    pass


class CropParamResponse(CropParamBase):
    id: int
    crop_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CropWithParamsResponse(CropResponse):
    params: Optional[CropParamResponse] = None


class ActiveConfigBase(BaseModel):
    config_json: dict
    crop_id: Optional[int] = None


class ActiveConfigCreate(ActiveConfigBase):
    pass


class ActiveConfigUpdate(BaseModel):
    config_json: Optional[dict] = None
    crop_id: Optional[int] = None


class ActiveConfigResponse(ActiveConfigBase):
    id: int
    version: int
    applied_by: Optional[int] = None
    applied_at: datetime
    is_active: bool
    esp32_confirmed: bool
    esp32_confirmed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConfigHistoryResponse(BaseModel):
    id: int
    config_json: dict
    version: int
    crop_id: Optional[int] = None
    changed_by: Optional[int] = None
    change_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReadingBase(BaseModel):
    timestamp: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    soil_adc: List[int] = Field(default_factory=lambda: [0]*6)
    soil_pct: List[float] = Field(default_factory=lambda: [0.0]*6)
    soil_ok: List[bool] = Field(default_factory=lambda: [True]*6)
    fan_1_state: bool = False
    fan_2_state: bool = False
    humidifier_1_state: bool = False
    humidifier_2_state: bool = False
    pump_state: bool = False
    rssi: Optional[int] = None
    device_id: Optional[str] = None
    sequence: Optional[int] = None


class ReadingCreate(ReadingBase):
    pass


class ReadingResponse(ReadingBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ActuatorLogResponse(BaseModel):
    id: int
    timestamp: datetime
    actuator: str
    state: bool
    triggered_by: Optional[str] = None
    reason: Optional[str] = None
    duration_seconds: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class EventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EventBase(BaseModel):
    severity: EventSeverity
    code: str = Field(..., max_length=50)
    message: str
    details: Optional[dict] = None


class EventCreate(EventBase):
    pass


class EventResponse(EventBase):
    id: int
    timestamp: datetime
    acknowledged: bool
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PhotoBase(BaseModel):
    timestamp: datetime
    path: str
    filename: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    sequence: Optional[int] = None
    chunks_received: int = 0
    chunks_total: Optional[int] = None
    is_complete: bool = False
    device_id: Optional[str] = None


class PhotoResponse(PhotoBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class DeviceResponse(BaseModel):
    id: int
    device_id: str
    device_type: str
    name: Optional[str] = None
    last_seen: Optional[datetime] = None
    rssi: Optional[int] = None
    firmware_version: Optional[str] = None
    config_version: Optional[int] = None
    is_online: bool
    device_metadata: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class TelemetrySnapshot(BaseModel):
    timestamp: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    soil_sensors: List[dict] = Field(default_factory=list)
    soil_avg_row_a: Optional[float] = None
    soil_avg_row_b: Optional[float] = None
    soil_avg_general: Optional[float] = None
    actuators: dict = Field(default_factory=dict)
    rssi: Optional[int] = None
    device_id: Optional[str] = None
    sequence: Optional[int] = None
    last_update: datetime


class SystemStatus(BaseModel):
    field_esp32_online: bool
    gateway_esp32_online: bool
    camera_online: bool
    last_telemetry: Optional[datetime] = None
    last_photo: Optional[datetime] = None
    active_config_version: Optional[int] = None
    active_crop: Optional[str] = None
    irrigation_enabled: bool = False
    alerts_count: int = 0