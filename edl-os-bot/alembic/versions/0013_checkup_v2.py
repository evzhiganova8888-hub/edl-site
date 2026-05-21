"""add Checkup v2 schema: answer types, figjam_url (ТЗ §12).

Revision ID: 0013_checkup_v2
Revises: 0012_quiz_submissions
Create Date: 2026-05-21 12:00:00.000000

Аддитивная миграция (все колонки NULLABLE или с DEFAULT) — старые
checkup_answers с answer_type=NULL валидны; код v2 трактует их как
'short_text' (legacy v1 answers).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_checkup_v2"
down_revision: Union[str, None] = "0012_quiz_submissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CheckupAnswer extensions
    op.add_column(
        "checkup_answers",
        sa.Column("answer_type", sa.Text(), nullable=True),
    )
    op.add_column(
        "checkup_answers",
        sa.Column("answer_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "checkup_answers",
        sa.Column("answer_numeric", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "checkup_answers",
        sa.Column(
            "answer_skipped",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Application: FigJam URL (ТЗ §9.2)
    op.add_column(
        "applications",
        sa.Column("figjam_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "figjam_url")
    op.drop_column("checkup_answers", "answer_skipped")
    op.drop_column("checkup_answers", "answer_numeric")
    op.drop_column("checkup_answers", "answer_score")
    op.drop_column("checkup_answers", "answer_type")
