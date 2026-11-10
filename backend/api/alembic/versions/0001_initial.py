"""Initial greenhouse schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "crops",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_crops_id", "crops", ["id"])
    op.create_index("ix_crops_name", "crops", ["name"], unique=True)

    op.create_table(
        "crop_params",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("crop_id", sa.Integer(), sa.ForeignKey("crops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("temp_min", sa.Float(), nullable=True),
        sa.Column("temp_max", sa.Float(), nullable=True),
        sa.Column("temp_night_min", sa.Float(), nullable=True),
        sa.Column("temp_night_max", sa.Float(), nullable=True),
        sa.Column("humidity_min", sa.Float(), nullable=True),
        sa.Column("humidity_max", sa.Float(), nullable=True),
        sa.Column("soil_moisture_min_pct", sa.Integer(), nullable=True),
        sa.Column("soil_moisture_max_pct", sa.Integer(), nullable=True),
        sa.Column("hysteresis_temp_on", sa.Float(), nullable=True),
        sa.Column("hysteresis_temp_off", sa.Float(), nullable=True),
        sa.Column("hysteresis_humidity_on", sa.Float(), nullable=True),
        sa.Column("hysteresis_humidity_off", sa.Float(), nullable=True),
        sa.Column("hysteresis_soil_on", sa.Integer(), nullable=True),
        sa.Column("hysteresis_soil_off", sa.Integer(), nullable=True),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_crop_params_id", "crop_params", ["id"])

    op.create_table(
        "active_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("crop_id", sa.Integer(), sa.ForeignKey("crops.id", ondelete="SET NULL"), nullable=True),
        sa.Column("applied_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("esp32_confirmed", sa.Boolean(), nullable=True),
        sa.Column("esp32_confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_active_config_id", "active_config", ["id"])

    op.create_table(
        "config_history",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("crop_id", sa.Integer(), sa.ForeignKey("crops.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("change_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_config_history_id", "config_history", ["id"])

    op.create_table(
        "readings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("humidity", sa.Float(), nullable=True),
        sa.Column("pressure", sa.Float(), nullable=True),
        sa.Column("soil_adc_a1", sa.Integer(), nullable=True),
        sa.Column("soil_adc_a2", sa.Integer(), nullable=True),
        sa.Column("soil_adc_a3", sa.Integer(), nullable=True),
        sa.Column("soil_adc_b1", sa.Integer(), nullable=True),
        sa.Column("soil_adc_b2", sa.Integer(), nullable=True),
        sa.Column("soil_adc_b3", sa.Integer(), nullable=True),
        sa.Column("soil_pct_a1", sa.Float(), nullable=True),
        sa.Column("soil_pct_a2", sa.Float(), nullable=True),
        sa.Column("soil_pct_a3", sa.Float(), nullable=True),
        sa.Column("soil_pct_b1", sa.Float(), nullable=True),
        sa.Column("soil_pct_b2", sa.Float(), nullable=True),
        sa.Column("soil_pct_b3", sa.Float(), nullable=True),
        sa.Column("soil_ok_a1", sa.Boolean(), nullable=True),
        sa.Column("soil_ok_a2", sa.Boolean(), nullable=True),
        sa.Column("soil_ok_a3", sa.Boolean(), nullable=True),
        sa.Column("soil_ok_b1", sa.Boolean(), nullable=True),
        sa.Column("soil_ok_b2", sa.Boolean(), nullable=True),
        sa.Column("soil_ok_b3", sa.Boolean(), nullable=True),
        sa.Column("fan_1_state", sa.Boolean(), nullable=True),
        sa.Column("fan_2_state", sa.Boolean(), nullable=True),
        sa.Column("humidifier_1_state", sa.Boolean(), nullable=True),
        sa.Column("humidifier_2_state", sa.Boolean(), nullable=True),
        sa.Column("pump_state", sa.Boolean(), nullable=True),
        sa.Column("rssi", sa.Integer(), nullable=True),
        sa.Column("device_id", sa.String(length=50), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=True),
    )
    op.create_index("ix_readings_id", "readings", ["id"])
    op.create_index("ix_readings_timestamp", "readings", ["timestamp"])
    op.create_index("ix_readings_timestamp_desc", "readings", [sa.text("timestamp DESC")])

    op.create_table(
        "actuator_log",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("actuator", sa.String(length=50), nullable=False),
        sa.Column("state", sa.Boolean(), nullable=False),
        sa.Column("triggered_by", sa.String(length=50), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
    )
    op.create_index("ix_actuator_log_id", "actuator_log", ["id"])
    op.create_index("ix_actuator_log_timestamp", "actuator_log", ["timestamp"])
    op.create_index("ix_actuator_log_actuator", "actuator_log", ["actuator"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=True),
        sa.Column("acknowledged_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_events_id", "events", ["id"])
    op.create_index("ix_events_timestamp", "events", ["timestamp"])
    op.create_index("ix_events_severity", "events", ["severity"])
    op.create_index("ix_events_code", "events", ["code"])

    op.create_table(
        "photos",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("chunks_received", sa.Integer(), nullable=True),
        sa.Column("chunks_total", sa.Integer(), nullable=True),
        sa.Column("is_complete", sa.Boolean(), nullable=True),
        sa.Column("device_id", sa.String(length=50), nullable=True),
    )
    op.create_index("ix_photos_id", "photos", ["id"])
    op.create_index("ix_photos_timestamp", "photos", ["timestamp"])

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("device_id", sa.String(length=50), nullable=False),
        sa.Column("device_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("rssi", sa.Integer(), nullable=True),
        sa.Column("firmware_version", sa.String(length=50), nullable=True),
        sa.Column("config_version", sa.Integer(), nullable=True),
        sa.Column("is_online", sa.Boolean(), nullable=True),
        sa.Column("device_metadata", sa.JSON(), nullable=True),
    )
    op.create_index("ix_devices_id", "devices", ["id"])
    op.create_index("ix_devices_device_id", "devices", ["device_id"], unique=True)
    op.create_index("ix_devices_last_seen", "devices", ["last_seen"])


def downgrade() -> None:
    op.drop_table("devices")
    op.drop_table("photos")
    op.drop_table("events")
    op.drop_table("actuator_log")
    op.drop_table("readings")
    op.drop_table("config_history")
    op.drop_table("active_config")
    op.drop_table("crop_params")
    op.drop_table("crops")
    op.drop_table("users")
