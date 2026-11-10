"""Persistent login throttle counters.

Revision ID: 0003_auth_throttle
Revises: 0002_push_subscriptions
Create Date: 2026-11-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_auth_throttle"
down_revision: Union[str, None] = "0002_push_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_throttle",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("scope", "key", name="uq_auth_throttle_scope_key"),
    )
    op.create_index("ix_auth_throttle_id", "auth_throttle", ["id"])
    op.create_index("ix_auth_throttle_updated_at", "auth_throttle", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_throttle_updated_at", table_name="auth_throttle")
    op.drop_index("ix_auth_throttle_id", table_name="auth_throttle")
    op.drop_table("auth_throttle")
