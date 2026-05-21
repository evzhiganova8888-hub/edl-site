"""coupons + coupon_usages (ТЗ Чекап Plus v2.0 §8, упрощённая v1.0).

Жёсткий TTL: купон действует ровно (expires_at - issued_at), типично
24 часа. См. core/coupon_engine.py — issuance, activation, expiry.

Revision ID: 0014_coupons
Revises: 0013_checkup_v2
Create Date: 2026-05-21 16:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_coupons"
down_revision: Union[str, None] = "0013_checkup_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id"),
            nullable=True,
        ),
        sa.Column(
            "target_product",
            sa.Text(),
            nullable=False,
            server_default="diagnostika",
        ),
        sa.Column("discount_pct", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("original_price_rub", sa.Integer(), nullable=False),
        sa.Column("discounted_price_rub", sa.Integer(), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.Text(), nullable=False, server_default="active"
        ),
    )
    op.create_index(
        "idx_coupons_user_status", "coupons", ["user_id", "status"]
    )
    op.create_index("idx_coupons_expires_at", "coupons", ["expires_at"])
    op.create_index("idx_coupons_code", "coupons", ["code"], unique=True)

    op.create_table(
        "coupon_usages",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "coupon_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coupons.id"),
            nullable=False,
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("activated_via", sa.Text(), nullable=False),
        sa.Column(
            "diagnostika_application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_coupon_usages_coupon", "coupon_usages", ["coupon_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_coupon_usages_coupon", table_name="coupon_usages")
    op.drop_table("coupon_usages")
    op.drop_index("idx_coupons_code", table_name="coupons")
    op.drop_index("idx_coupons_expires_at", table_name="coupons")
    op.drop_index("idx_coupons_user_status", table_name="coupons")
    op.drop_table("coupons")
