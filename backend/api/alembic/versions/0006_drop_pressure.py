"""Remove the atmospheric pressure reading from the greenhouse telemetry.

Revision ID: 0006_drop_pressure
Revises: 0005_single_humidifier
Create Date: 2026-11-19

The field node reads a DHT11, which has no barometer. Keeping a column that is
always null only misleads the dashboard, so the reading is removed from the
stored telemetry. Outdoor weather pressure (OpenWeather) lives in its own
tables and is not affected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_drop_pressure"
down_revision: Union[str, None] = "0005_single_humidifier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("readings") as batch_op:
        batch_op.drop_column("pressure")


def downgrade() -> None:
    with op.batch_alter_table("readings") as batch_op:
        batch_op.add_column(sa.Column("pressure", sa.Float(), nullable=True))
