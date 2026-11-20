"""Single humidifier: drop the redundant humidifier_2_state column.

Revision ID: 0005_single_humidifier
Revises: 0004_audit_logs
Create Date: 2026-11-19

Both humidifiers were always driven by the same humidity hysteresis, so this
column only mirrored humidifier_1_state. The greenhouse now has a single
misting unit and the field firmware no longer reports a second output.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_single_humidifier"
down_revision: Union[str, None] = "0004_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("readings") as batch_op:
        batch_op.drop_column("humidifier_2_state")


def downgrade() -> None:
    with op.batch_alter_table("readings") as batch_op:
        batch_op.add_column(sa.Column("humidifier_2_state", sa.Boolean(), nullable=True))
