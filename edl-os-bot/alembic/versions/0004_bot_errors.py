"""add bot_errors table for VoC loop (§E.3 ТЗ v3.1).

Revision ID: 0004_bot_errors
Revises: 0003_feature_flags
Create Date: 2026-05-12 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_bot_errors"
down_revision: Union[str, None] = "0003_feature_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bot_errors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("message_log_id", sa.BigInteger(), sa.ForeignKey("messages_log.id"), nullable=True),
        sa.Column("user_comment", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("prompt_patched", sa.Boolean(), server_default=sa.false()),
    )
    op.create_index(
        "idx_bot_errors_unresolved",
        "bot_errors",
        ["reported_at"],
        postgresql_where=sa.text("reviewed_at IS NULL"),
    )
    op.create_index("idx_bot_errors_user", "bot_errors", ["user_id", "reported_at"])


def downgrade() -> None:
    op.drop_index("idx_bot_errors_user", table_name="bot_errors")
    op.drop_index("idx_bot_errors_unresolved", table_name="bot_errors")
    op.drop_table("bot_errors")
