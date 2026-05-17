"""add lead_stage columns to users (F6).

Revision ID: 0009_add_lead_stage
Revises: 0008_widget_sessions
Create Date: 2026-05-18 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_add_lead_stage"
down_revision: Union[str, None] = "0008_widget_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("lead_stage", sa.Text(), nullable=True, server_default="cold"),
    )
    op.add_column(
        "users",
        sa.Column("lead_stage_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "lead_stage_updated_at")
    op.drop_column("users", "lead_stage")
