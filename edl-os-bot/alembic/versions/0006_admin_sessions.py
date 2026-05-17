"""add admin_sessions table + checkup fields on Application.

Revision ID: 0006_admin_sessions
Revises: 0005_feedback
Create Date: 2026-05-16 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_admin_sessions"
down_revision: Union[str, None] = "0005_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("granted_by", sa.Text(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_admin_sessions_tg", "admin_sessions", ["telegram_id"])

    # Checkup fields on applications
    op.add_column("applications", sa.Column("checkup_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("checkup_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("checkup_pdf_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "checkup_pdf_url")
    op.drop_column("applications", "checkup_completed_at")
    op.drop_column("applications", "checkup_started_at")
    op.drop_index("idx_admin_sessions_tg", table_name="admin_sessions")
    op.drop_table("admin_sessions")
