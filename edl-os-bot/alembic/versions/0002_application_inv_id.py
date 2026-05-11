"""add Application.inv_id sequence for Robokassa InvId.

Revision ID: 0002_application_inv_id
Revises: 0001_initial
Create Date: 2026-05-11 17:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_application_inv_id"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS applications_inv_id_seq START 1000")
    op.add_column(
        "applications",
        sa.Column(
            "inv_id",
            sa.BigInteger(),
            nullable=True,
            server_default=sa.text("nextval('applications_inv_id_seq')"),
        ),
    )
    op.execute(
        "UPDATE applications SET inv_id = nextval('applications_inv_id_seq') WHERE inv_id IS NULL"
    )
    op.alter_column("applications", "inv_id", nullable=False)
    op.create_unique_constraint("uq_applications_inv_id", "applications", ["inv_id"])


def downgrade() -> None:
    op.drop_constraint("uq_applications_inv_id", "applications", type_="unique")
    op.drop_column("applications", "inv_id")
    op.execute("DROP SEQUENCE IF EXISTS applications_inv_id_seq")
