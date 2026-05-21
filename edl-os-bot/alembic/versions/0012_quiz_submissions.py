"""Mini-Чекап v2: quiz_submissions + users.quiz_completed_at + users.quiz_stage.

Revision ID: 0012_quiz_submissions
Revises: 0011_plus_video_fields
Create Date: 2026-05-21 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_quiz_submissions"
down_revision: Union[str, None] = "0011_plus_video_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quiz_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("widget_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("segment", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("stage_confidence", sa.Text(), nullable=False, server_default="high"),
        sa.Column("outlier_flag", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("layer_scores", postgresql.JSONB(), nullable=False),
        sa.Column("answers", postgresql.JSONB(), nullable=False),
        sa.Column("growth_points", postgresql.JSONB(), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("consent_marketing_at_submit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_quiz_submissions_user_id", "quiz_submissions", ["user_id"])
    op.create_index("ix_quiz_submissions_widget_session_id", "quiz_submissions", ["widget_session_id"])
    op.create_index("ix_quiz_submissions_created_at", "quiz_submissions", ["created_at"])

    op.add_column("users", sa.Column("quiz_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("quiz_stage", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "quiz_stage")
    op.drop_column("users", "quiz_completed_at")
    op.drop_index("ix_quiz_submissions_created_at", table_name="quiz_submissions")
    op.drop_index("ix_quiz_submissions_widget_session_id", table_name="quiz_submissions")
    op.drop_index("ix_quiz_submissions_user_id", table_name="quiz_submissions")
    op.drop_table("quiz_submissions")
