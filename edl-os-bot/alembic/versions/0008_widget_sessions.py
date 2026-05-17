"""add widget_sessions table and user widget columns (F4).

Revision ID: 0008_widget_sessions
Revises: 0007_checkup_answers
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_widget_sessions"
down_revision: Union[str, None] = "0007_checkup_answers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "widget_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("source_channel", sa.Text(), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_widget_sessions_tg", "widget_sessions", ["telegram_id"])

    op.add_column("users", sa.Column("source_channel", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("widget_session_id", postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "widget_session_id")
    op.drop_column("users", "source_channel")
    op.drop_index("idx_widget_sessions_tg", table_name="widget_sessions")
    op.drop_table("widget_sessions")
