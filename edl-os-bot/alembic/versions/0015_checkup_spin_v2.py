"""SPIN-Чекап v2.0 — расширение applications для нового флоу (ТЗ §10.1).

Добавляются:
- archetype — ключ из 6 MVP-архетипов или fallback (anna_command по умолчанию)
- report_id — текстовый идентификатор отчёта (EDL-CHK-YYYY-NNNN)
- spin_failsafe_warning_sent_at — момент отправки fail-safe сообщения
  «5 мин без ввода» (ТЗ §3.6), чтобы не дублировать

Дополнительно для checkup_answers:
- is_decline — клиент явно ответил «не знаю / не считаем» (ТЗ §3.6)
- decline_reason — какой из markers сработал

Все колонки NULLABLE — миграция чисто аддитивная, не ломает старые
20-quiz Чекапы.

Revision ID: 0015_checkup_spin_v2
Revises: 0014_coupons
Create Date: 2026-05-22 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_checkup_spin_v2"
down_revision: Union[str, None] = "0014_coupons"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # applications: новые колонки
    op.add_column("applications", sa.Column("archetype", sa.Text(), nullable=True))
    op.add_column("applications", sa.Column("report_id", sa.Text(), nullable=True))
    op.add_column(
        "applications",
        sa.Column(
            "spin_failsafe_warning_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Индекс для быстрого поиска по report_id (он уникален, но допускаем NULL)
    op.create_index(
        "idx_applications_report_id", "applications", ["report_id"], unique=False
    )

    # checkup_answers: маркеры decline
    op.add_column(
        "checkup_answers",
        sa.Column(
            "is_decline",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "checkup_answers",
        sa.Column("decline_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("checkup_answers", "decline_reason")
    op.drop_column("checkup_answers", "is_decline")
    op.drop_index("idx_applications_report_id", table_name="applications")
    op.drop_column("applications", "spin_failsafe_warning_sent_at")
    op.drop_column("applications", "report_id")
    op.drop_column("applications", "archetype")
