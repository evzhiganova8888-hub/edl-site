"""add feature_flags table for runtime toggles (§10 ТЗ v3).

Revision ID: 0003_feature_flags
Revises: 0002_application_inv_id
Create Date: 2026-05-11 17:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_feature_flags"
down_revision: Union[str, None] = "0002_application_inv_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute(
        "INSERT INTO feature_flags (key, enabled, updated_by) "
        "VALUES ('vitaconsult_public', false, 'system') "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("feature_flags")
