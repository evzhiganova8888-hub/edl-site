"""add checkup progress columns to applications (F7).

Revision ID: 0010_add_checkup_progress
Revises: 0009_add_lead_stage
Create Date: 2026-05-18 00:02:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_add_checkup_progress"
down_revision: Union[str, None] = "0009_add_lead_stage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("checkup_current_question_index", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "applications",
        sa.Column("checkup_last_active_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "checkup_last_active_at")
    op.drop_column("applications", "checkup_current_question_index")
