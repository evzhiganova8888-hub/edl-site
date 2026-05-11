"""initial schema — BOT_TZ_v3.md §15.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-11 16:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\"")

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("telegram_username", sa.Text()),
        sa.Column("first_name", sa.Text()),
        sa.Column("last_name", sa.Text()),
        sa.Column("segment", sa.Text()),
        sa.Column("sub_profile", sa.Text()),
        sa.Column("stage", sa.Text(), server_default="cold"),
        sa.Column("quiz_score", sa.Integer()),
        sa.Column("consent_pd_given_at", sa.DateTime(timezone=True)),
        sa.Column("consent_pd_version", sa.Text()),
        sa.Column("consent_marketing_given_at", sa.DateTime(timezone=True)),
        sa.Column("consent_offer_accepted_at", sa.DateTime(timezone=True)),
        sa.Column("email", sa.Text()),
        sa.Column("phone", sa.Text()),
        sa.Column("company_name", sa.Text()),
        sa.Column("company_size", sa.Integer()),
        sa.Column("company_revenue_range", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_users_segment", "users", ["segment"])

    op.create_table(
        "applications",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="new"),
        sa.Column("source", sa.Text()),
        sa.Column("cta_location", sa.Text()),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("payment_succeeded_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("refund_eligible_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_applications_user_status", "applications", ["user_id", "status"])

    op.create_table(
        "payments",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id")),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("amount_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.Text(), server_default="RUB"),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_invoice_id", sa.Text()),
        sa.Column("provider_payment_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("fiscal_receipt_url", sa.Text()),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("refunded_at", sa.DateTime(timezone=True)),
        sa.Column("refund_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_payments_user_status", "payments", ["user_id", "status"])

    op.create_table(
        "refunds",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id")),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("status", sa.Text(), server_default="requested"),
        sa.Column("reason", sa.Text()),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.BigInteger()),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_events_occurred_at", "events", ["occurred_at"])

    op.create_table(
        "messages_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.BigInteger()),
        sa.Column("direction", sa.Text()),
        sa.Column("text", sa.Text()),
        sa.Column("llm_tokens", sa.Integer()),
        sa.Column("sticker_sent", sa.Boolean(), server_default=sa.false()),
        sa.Column("vat_topic_mentioned", sa.Boolean(), server_default=sa.false()),
        sa.Column("intent_detected", sa.Text()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_messages_log_user", "messages_log", ["user_id", "occurred_at"])

    op.create_table(
        "pd_access_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("actor", sa.Text()),
        sa.Column("user_id", sa.BigInteger()),
        sa.Column("action", sa.Text()),
        sa.Column("fields", postgresql.ARRAY(sa.String())),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pd_access_log")
    op.drop_index("idx_messages_log_user", table_name="messages_log")
    op.drop_table("messages_log")
    op.drop_index("idx_events_occurred_at", table_name="events")
    op.drop_table("events")
    op.drop_table("refunds")
    op.drop_index("idx_payments_user_status", table_name="payments")
    op.drop_table("payments")
    op.drop_index("idx_applications_user_status", table_name="applications")
    op.drop_table("applications")
    op.drop_index("idx_users_segment", table_name="users")
    op.drop_table("users")
