"""add whitepaper_leads table.

Revision ID: 0008_whitepaper_leads
Revises: 0007_checkup_answers
Create Date: 2026-05-18 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_whitepaper_leads"
down_revision: Union[str, None] = "0007_checkup_answers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whitepaper_leads",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("pdf", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_hash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_whitepaper_leads_email", "whitepaper_leads", ["email", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_whitepaper_leads_email", table_name="whitepaper_leads")
    op.drop_table("whitepaper_leads")
