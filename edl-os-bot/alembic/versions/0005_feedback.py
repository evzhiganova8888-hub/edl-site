"""add feedback table + user.wants_followup_report flag (beta 12.05-19.05).

Revision ID: 0005_feedback
Revises: 0004_bot_errors
Create Date: 2026-05-12 19:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_feedback"
down_revision: Union[str, None] = "0004_bot_errors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        # Шаг: welcome / audit / quiz / offer / payment / ai_reply / refund / privacy / other
        sa.Column("step", sa.Text(), nullable=False),
        # Категория: bug / missing / idea / praise
        sa.Column("category", sa.Text(), nullable=False),
        # Severity: low / med / high (default med, можно не задавать)
        sa.Column("severity", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
    )
    op.create_index(
        "idx_feedback_unresolved",
        "feedback",
        ["reported_at"],
        postgresql_where=sa.text("reviewed_at IS NULL"),
    )
    op.create_index(
        "idx_feedback_step_category", "feedback", ["step", "category"]
    )

    # Email-подписка на отчёт-итог по результатам бета-периода
    op.add_column(
        "users",
        sa.Column(
            "wants_followup_report",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "wants_followup_report")
    op.drop_index("idx_feedback_step_category", table_name="feedback")
    op.drop_index("idx_feedback_unresolved", table_name="feedback")
    op.drop_table("feedback")
