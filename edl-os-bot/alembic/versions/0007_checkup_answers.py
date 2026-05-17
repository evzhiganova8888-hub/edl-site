"""add checkup_answers table.

Revision ID: 0007_checkup_answers
Revises: 0006_admin_sessions
Create Date: 2026-05-16 10:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_checkup_answers"
down_revision: Union[str, None] = "0006_admin_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "checkup_answers",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_key", sa.Text(), nullable=False),
        sa.Column("layer", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("quality_passed", sa.Boolean(), nullable=False, default=False),
        sa.Column("quality_notes", sa.Text(), nullable=True),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_checkup_answers_app", "checkup_answers", ["application_id"])
    op.create_index(
        "uq_checkup_answers_app_q",
        "checkup_answers",
        ["application_id", "question_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_checkup_answers_app_q", table_name="checkup_answers")
    op.drop_index("idx_checkup_answers_app", table_name="checkup_answers")
    op.drop_table("checkup_answers")
