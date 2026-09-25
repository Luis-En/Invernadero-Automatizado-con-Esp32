from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Index, JSON
)
from sqlalchemy.orm import declarative_base, relationship, backref
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="viewer", nullable=False)  # viewer, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Crop(Base):
    __tablename__ = "crops"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CropParam(Base):
    __tablename__ = "crop_params"
    id = Column(Integer, primary_key=True, index=True)
    crop_id = Column(Integer, ForeignKey("crops.id", ondelete="CASCADE"), nullable=False)
    temp_min = Column(Float, nullable=True)
    temp_max = Column(Float, nullable=True)
    temp_night_min = Column(Float, nullable=True)
    temp_night_max = Column(Float, nullable=True)
    humidity_min = Column(Float, nullable=True)
    humidity_max = Column(Float, nullable=True)
    soil_moisture_min_pct = Column(Integer, nullable=True)
    soil_moisture_max_pct = Column(Integer, nullable=True)
    hysteresis_temp_on = Column(Float, nullable=True)
    hysteresis_temp_off = Column(Float, nullable=True)
    hysteresis_humidity_on = Column(Float, nullable=True)
    hysteresis_humidity_off = Column(Float, nullable=True)
    hysteresis_soil_on = Column(Integer, nullable=True)
    hysteresis_soil_off = Column(Integer, nullable=True)
    source_reference = Column(String(255), nullable=True)
    source_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    crop = relationship("Crop", backref=backref("params", uselist=False, cascade="all, delete-orphan"))


class ActiveConfig(Base):
    __tablename__ = "active_config"
    id = Column(Integer, primary_key=True, index=True)
    config_json = Column(JSON, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    crop_id = Column(Integer, ForeignKey("crops.id", ondelete="SET NULL"), nullable=True)
    applied_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    esp32_confirmed = Column(Boolean, default=False)
    esp32_confirmed_at = Column(DateTime, nullable=True)

    crop = relationship("Crop")
    applied_by_user = relationship("User")


class ConfigHistory(Base):
    __tablename__ = "config_history"
    id = Column(Integer, primary_key=True, index=True)
    config_json = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False)
    crop_id = Column(Integer, ForeignKey("crops.id", ondelete="SET NULL"), nullable=True)
    changed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Reading(Base):
    __tablename__ = "readings"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    soil_adc_a1 = Column(Integer, nullable=True)
    soil_adc_a2 = Column(Integer, nullable=True)
    soil_adc_a3 = Column(Integer, nullable=True)
    soil_adc_b1 = Column(Integer, nullable=True)
    soil_adc_b2 = Column(Integer, nullable=True)
    soil_adc_b3 = Column(Integer, nullable=True)
    soil_pct_a1 = Column(Float, nullable=True)
    soil_pct_a2 = Column(Float, nullable=True)
    soil_pct_a3 = Column(Float, nullable=True)
    soil_pct_b1 = Column(Float, nullable=True)
    soil_pct_b2 = Column(Float, nullable=True)
    soil_pct_b3 = Column(Float, nullable=True)
    soil_ok_a1 = Column(Boolean, default=True)
    soil_ok_a2 = Column(Boolean, default=True)
    soil_ok_a3 = Column(Boolean, default=True)
    soil_ok_b1 = Column(Boolean, default=True)
    soil_ok_b2 = Column(Boolean, default=True)
    soil_ok_b3 = Column(Boolean, default=True)
    fan_1_state = Column(Boolean, default=False)
    fan_2_state = Column(Boolean, default=False)
    humidifier_1_state = Column(Boolean, default=False)
    humidifier_2_state = Column(Boolean, default=False)
    pump_state = Column(Boolean, default=False)
    rssi = Column(Integer, nullable=True)
    device_id = Column(String(50), nullable=True)
    sequence = Column(Integer, nullable=True)

    __table_args__ = (
        Index('ix_readings_timestamp_desc', timestamp.desc()),
    )


class ActuatorLog(Base):
    __tablename__ = "actuator_log"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    actuator = Column(String(50), nullable=False, index=True)
    state = Column(Boolean, nullable=False)
    triggered_by = Column(String(50), nullable=True)  # auto, manual, safety
    reason = Column(String(255), nullable=True)
    duration_seconds = Column(Integer, nullable=True)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    severity = Column(String(20), nullable=False, index=True)  # info, warning, critical
    code = Column(String(50), nullable=False, index=True)
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)


class Photo(Base):
    __tablename__ = "photos"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    path = Column(String(500), nullable=False)
    filename = Column(String(255), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    sequence = Column(Integer, nullable=True)
    chunks_received = Column(Integer, default=0)
    chunks_total = Column(Integer, nullable=True)
    is_complete = Column(Boolean, default=False)
    device_id = Column(String(50), nullable=True)


class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, index=True, nullable=False)
    device_type = Column(String(50), nullable=False)  # field, gateway, camera
    name = Column(String(100), nullable=True)
    last_seen = Column(DateTime, nullable=True, index=True)
    rssi = Column(Integer, nullable=True)
    firmware_version = Column(String(50), nullable=True)
    config_version = Column(Integer, nullable=True)
    is_online = Column(Boolean, default=False)
    device_metadata = Column(JSON, nullable=True)