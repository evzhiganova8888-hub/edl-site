"""add Plus video fields to applications (F8).

Revision ID: 0011_plus_video_fields
Revises: 0010_add_checkup_progress
Create Date: 2026-05-18 00:03:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_plus_video_fields"
down_revision: Union[str, None] = "0010_add_checkup_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("plus_video_recommended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("plus_video_uploaded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("plus_video_url", sa.Text(), nullable=True))
    op.add_column("applications", sa.Column("plus_video_sent_to_client_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "plus_video_sent_to_client_at")
    op.drop_column("applications", "plus_video_url")
    op.drop_column("applications", "plus_video_uploaded_at")
    op.drop_column("applications", "plus_video_recommended_at")
