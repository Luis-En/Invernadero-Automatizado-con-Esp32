from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from enum import Enum

from app.password_policy import validate_password_strength


class UserRole(str, Enum):
    VIEWER = "viewer"
    ADMIN = "admin"


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    role: UserRole = UserRole.VIEWER

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("El usuario debe tener al menos 3 caracteres")
        if any(char in cleaned for char in "\r\n\t\0"):
            raise ValueError("El usuario contiene caracteres no permitidos")
        return cleaned


class UserCreate(UserBase):
    # bcrypt only uses the first 72 bytes; rejecting longer input is clearer
    # than silently hashing a truncated password. Length is preferred over
    # forced character classes, which tend to produce predictable passwords.
    password: str = Field(..., min_length=12, max_length=72)

    @field_validator("password")
    @classmethod
    def bcrypt_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("La contraseña no puede superar 72 bytes en UTF-8")
        return value

    @model_validator(mode="after")
    def require_strong_password(self):
        errors = validate_password_strength(self.password, self.username)
        if errors:
            raise ValueError("; ".join(errors))
        return self


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)

    @field_validator("username")
    @classmethod
    def clean_login_username(cls, value: str) -> str:
        return value.strip()


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


DEFAULT_MAX_ON_SECONDS = {"fan": 7200, "humidifier": 7200, "pump": 900}
DEFAULT_MIN_OFF_SECONDS = {"fan": 0, "humidifier": 0, "pump": 300}
MAX_ON_LIMIT_SECONDS = 24 * 60 * 60


class TemperatureHysteresis(BaseModel):
    """Fan: ON at/above on_above, OFF at/below off_below."""

    on_above: float = Field(30.0, ge=-10.0, le=60.0)
    off_below: float = Field(27.5, ge=-10.0, le=60.0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.off_below >= self.on_above:
            raise ValueError("temp.off_below must be lower than temp.on_above")
        return self


class HumidityHysteresis(BaseModel):
    """Humidifier: ON at/below on_below, OFF at/above off_above."""

    on_below: float = Field(60.0, ge=0.0, le=100.0)
    off_above: float = Field(68.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.on_below >= self.off_above:
            raise ValueError("humidity.on_below must be lower than humidity.off_above")
        return self


class SoilHysteresis(BaseModel):
    """Pump: ON at/below on_below_pct, OFF at/above off_above_pct."""

    on_below_pct: float = Field(35.0, ge=0.0, le=100.0)
    off_above_pct: float = Field(45.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.on_below_pct >= self.off_above_pct:
            raise ValueError("soil.on_below_pct must be lower than soil.off_above_pct")
        return self


class HysteresisConfig(BaseModel):
    temp: TemperatureHysteresis = Field(default_factory=TemperatureHysteresis)
    humidity: HumidityHysteresis = Field(default_factory=HumidityHysteresis)
    soil: SoilHysteresis = Field(default_factory=SoilHysteresis)


class IrrigationConfig(BaseModel):
    enabled: bool = False


class MaxOnSeconds(BaseModel):
    fan: int = Field(DEFAULT_MAX_ON_SECONDS["fan"], ge=0, le=MAX_ON_LIMIT_SECONDS)
    humidifier: int = Field(DEFAULT_MAX_ON_SECONDS["humidifier"], ge=0, le=MAX_ON_LIMIT_SECONDS)
    pump: int = Field(DEFAULT_MAX_ON_SECONDS["pump"], ge=0, le=MAX_ON_LIMIT_SECONDS)

    @model_validator(mode="after")
    def _zero_means_default(self):
        # 0 is a configuration shorthand for "use the safe default", never an
        # unlimited ON time. Negative values are rejected by the Field bounds.
        for name in ("fan", "humidifier", "pump"):
            if getattr(self, name) == 0:
                setattr(self, name, DEFAULT_MAX_ON_SECONDS[name])
        return self


class MinOffSeconds(BaseModel):
    fan: int = Field(DEFAULT_MIN_OFF_SECONDS["fan"], ge=0, le=MAX_ON_LIMIT_SECONDS)
    humidifier: int = Field(DEFAULT_MIN_OFF_SECONDS["humidifier"], ge=0, le=MAX_ON_LIMIT_SECONDS)
    pump: int = Field(DEFAULT_MIN_OFF_SECONDS["pump"], ge=0, le=MAX_ON_LIMIT_SECONDS)


class SafetyConfig(BaseModel):
    max_on_seconds: MaxOnSeconds = Field(default_factory=MaxOnSeconds)
    min_off_seconds: MinOffSeconds = Field(default_factory=MinOffSeconds)


class ControlConfig(BaseModel):
    """Validated control document shared by the API, gateway and field node.

    Physical bounds live here so an out-of-range value can never reach an
    actuator. Unknown keys are ignored for forward compatibility.
    """

    model_config = ConfigDict(extra="ignore")

    version: int = Field(1, ge=0, le=65535)
    crop: str = Field("tomate", min_length=1, max_length=23)
    hysteresis: HysteresisConfig = Field(default_factory=HysteresisConfig)
    irrigation: IrrigationConfig = Field(default_factory=IrrigationConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)


class ActiveConfigBase(BaseModel):
    config_json: ControlConfig
    crop_id: Optional[int] = None


class ActiveConfigCreate(ActiveConfigBase):
    pass


class ActiveConfigUpdate(BaseModel):
    config_json: Optional[ControlConfig] = None
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


class TelemetryPayload(BaseModel):
    """Validated telemetry posted by the serial bridge.

    A frozen or misconfigured clock can silently corrupt the history, so the
    timestamp is normalized to UTC and absurd dates are rejected here instead
    of downstream.
    """

    model_config = ConfigDict(extra="ignore")

    timestamp: datetime
    temperature: Optional[float] = Field(None, ge=-40.0, le=80.0)
    humidity: Optional[float] = Field(None, ge=0.0, le=100.0)
    pressure: Optional[float] = Field(None, ge=300.0, le=1100.0)
    soil_adc: List[int] = Field(default_factory=lambda: [0] * 6)
    soil_pct: List[float] = Field(default_factory=lambda: [0.0] * 6)
    soil_ok: List[bool] = Field(default_factory=lambda: [False] * 6)
    fan_1_state: bool = False
    fan_2_state: bool = False
    humidifier_1_state: bool = False
    humidifier_2_state: bool = False
    pump_state: bool = False
    rssi: Optional[int] = Field(None, ge=-120, le=10)
    device_id: Optional[str] = Field(None, max_length=50)
    sequence: Optional[int] = Field(None, ge=0, le=65535)

    @field_validator("soil_adc")
    @classmethod
    def _soil_adc_length(cls, value: List[int]) -> List[int]:
        if len(value) != 6:
            raise ValueError("soil_adc must contain exactly 6 values")
        for sample in value:
            if sample < 0 or sample > 4095:
                raise ValueError("soil_adc values must be within 0..4095")
        return value

    @field_validator("soil_pct")
    @classmethod
    def _soil_pct_length(cls, value: List[float]) -> List[float]:
        if len(value) != 6:
            raise ValueError("soil_pct must contain exactly 6 values")
        for sample in value:
            if sample < 0.0 or sample > 100.0:
                raise ValueError("soil_pct values must be within 0..100")
        return value

    @field_validator("soil_ok")
    @classmethod
    def _soil_ok_length(cls, value: List[bool]) -> List[bool]:
        if len(value) != 6:
            raise ValueError("soil_ok must contain exactly 6 values")
        return value

    @field_validator("timestamp", mode="before")
    @classmethod
    def _parse_timestamp(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
        return value

    @model_validator(mode="after")
    def _normalize_timestamp(self):
        ts = self.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ts = ts.astimezone(timezone.utc)
        # Reject a clock that is clearly wrong (year 1970/2100) or far in the
        # future. A few minutes of skew is tolerated for devices without NTP.
        if ts.year < 2000 or ts.year > 2100:
            raise ValueError("timestamp outside the accepted range (2000..2100)")
        if ts > datetime.now(timezone.utc) + timedelta(minutes=10):
            raise ValueError("timestamp is in the future")
        self.timestamp = ts
        return self


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
    # Irrigation assessment for the dashboard banner and notification panel.
    soil_avg_pct: Optional[float] = None
    soil_threshold_pct: Optional[float] = None
    soil_off_above_pct: Optional[float] = None
    irrigation_needed: bool = False
    valid_soil_sensors: int = 0
    telemetry_stale: bool = False


class PushKeys(BaseModel):
    p256dh: str = Field(..., min_length=16, max_length=200)
    auth: str = Field(..., min_length=8, max_length=100)


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(..., min_length=8, max_length=500)
    keys: PushKeys
    user_agent: Optional[str] = Field(None, max_length=255)


class PushSubscriptionDelete(BaseModel):
    endpoint: str = Field(..., min_length=8, max_length=500)


class PushSubscriptionResponse(BaseModel):
    id: int
    endpoint: str
    created_at: datetime
    last_seen: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class NotificationConfig(BaseModel):
    enabled: bool
    push_supported: bool
    vapid_public_key: Optional[str] = None
    check_interval_sec: int = 60
    reminder_hours: float = 6
    soil_on_below_pct: Optional[float] = None
    soil_off_above_pct: Optional[float] = None


class WeatherLocation(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    timezone_offset: Optional[int] = None


class WeatherCurrent(BaseModel):
    time: Optional[datetime] = None
    temperature: Optional[float] = None
    feels_like: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_gust: Optional[float] = None
    wind_deg: Optional[int] = None
    clouds: Optional[int] = None
    visibility: Optional[int] = None
    rain_1h: Optional[float] = None
    description: Optional[str] = None
    main: Optional[str] = None
    icon: Optional[str] = None
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None


class WeatherRainSummary(BaseModel):
    status: str
    summary: str
    next_6h_probability: float = 0.0
    next_24h_probability: float = 0.0
    next_24h_mm: float = 0.0
    first_rain_at: Optional[datetime] = None
    first_rain_probability: Optional[float] = None


class WeatherHour(BaseModel):
    dt: int
    time: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_deg: Optional[int] = None
    clouds: Optional[int] = None
    pop: float = 0.0
    rain_mm: float = 0.0
    description: Optional[str] = None
    main: Optional[str] = None
    icon: Optional[str] = None


class WeatherDay(BaseModel):
    date: str
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    humidity_avg: Optional[int] = None
    wind_max: Optional[float] = None
    pop_max: float = 0.0
    rain_mm: float = 0.0
    description: Optional[str] = None
    icon: Optional[str] = None


class WeatherOverview(BaseModel):
    configured: bool
    stale: bool = False
    error: Optional[str] = None
    fetched_at: Optional[datetime] = None
    hours: int = 48
    units: str = "metric"
    location: Optional[WeatherLocation] = None
    current: Optional[WeatherCurrent] = None
    rain: Optional[WeatherRainSummary] = None
    hourly: List[WeatherHour] = Field(default_factory=list)
    daily: List[WeatherDay] = Field(default_factory=list)


class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    resource: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict] = None

    model_config = ConfigDict(from_attributes=True)


class PublicSoilSensor(BaseModel):
    id: str
    pct: Optional[float] = None
    ok: bool = True
    row: str


class PublicTelemetry(BaseModel):
    timestamp: datetime
    last_update: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    soil_sensors: List[PublicSoilSensor] = Field(default_factory=list)
    soil_avg_row_a: Optional[float] = None
    soil_avg_row_b: Optional[float] = None
    soil_avg_general: Optional[float] = None
    actuators: Dict[str, bool] = Field(default_factory=dict)
    irrigation_enabled: bool = False
    irrigation_needed: bool = False
    # Public hysteresis thresholds: needed to explain the status colour
    # without exposing the rest of the configuration document.
    soil_threshold_pct: Optional[float] = None
    soil_off_above_pct: Optional[float] = None
    active_crop: Optional[str] = None
    telemetry_stale: bool = False


class PublicPhotoResponse(BaseModel):
    id: int
    timestamp: datetime
    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: int

    model_config = ConfigDict(from_attributes=True)


class PublicCropParams(BaseModel):
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    temp_night_min: Optional[float] = None
    temp_night_max: Optional[float] = None
    humidity_min: Optional[float] = None
    humidity_max: Optional[float] = None
    soil_moisture_min_pct: Optional[int] = None
    soil_moisture_max_pct: Optional[int] = None
    hysteresis_soil_on: Optional[int] = None
    hysteresis_soil_off: Optional[int] = None
    source_reference: Optional[str] = None
    source_url: Optional[str] = None


class PublicCropResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    params: Optional[PublicCropParams] = None