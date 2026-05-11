"""SQLAlchemy models — БД схема из BOT_TZ_v3.md §15."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    telegram_username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    segment: Mapped[str | None] = mapped_column(Text, index=True)
    sub_profile: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(Text, default="cold")
    quiz_score: Mapped[int | None] = mapped_column(Integer)
    consent_pd_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_pd_version: Mapped[str | None] = mapped_column(Text)
    consent_marketing_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_offer_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    company_name: Mapped[str | None] = mapped_column(Text)
    company_size: Mapped[int | None] = mapped_column(Integer)
    company_revenue_range: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    applications: Mapped[list[Application]] = relationship(back_populates="user")
    payments: Mapped[list[Payment]] = relationship(back_populates="user")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inv_id: Mapped[int] = mapped_column(
        BigInteger,
        autoincrement=True,
        unique=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(Text, nullable=False)  # demo|audit|diagnostic|...
    status: Mapped[str] = mapped_column(Text, default="new")
    source: Mapped[str | None] = mapped_column(Text)
    cta_location: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    payment_succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refund_eligible_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="applications")
    payments: Mapped[list[Payment]] = relationship(back_populates="application")

    __table_args__ = (
        Index("idx_applications_user_status", "user_id", "status"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id")
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(Text, default="RUB")
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_invoice_id: Mapped[str | None] = mapped_column(Text)
    provider_payment_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    fiscal_receipt_url: Mapped[str | None] = mapped_column(Text)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refund_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    application: Mapped[Application] = relationship(back_populates="payments")
    user: Mapped[User] = relationship(back_populates="payments")
    refunds: Mapped[list[Refund]] = relationship(back_populates="payment")

    __table_args__ = (
        Index("idx_payments_user_status", "user_id", "status"),
    )


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(Text, default="requested")
    reason: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    payment: Mapped[Payment] = relationship(back_populates="refunds")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    event: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class MessageLog(Base):
    __tablename__ = "messages_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    direction: Mapped[str] = mapped_column(Text)  # inbound|outbound
    text: Mapped[str | None] = mapped_column(Text)
    llm_tokens: Mapped[int | None] = mapped_column(Integer)
    sticker_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    vat_topic_mentioned: Mapped[bool] = mapped_column(Boolean, default=False)
    intent_detected: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_messages_log_user", "user_id", "occurred_at"),
    )


class PDAccessLog(Base):
    """Лог доступа к ПД (152-ФЗ §7.4)."""

    __tablename__ = "pd_access_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor: Mapped[str | None] = mapped_column(Text)  # 'system' | admin telegram id
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(Text)  # read|update|export|delete
    fields: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FeatureFlag(Base):
    """Runtime toggle (§10 ТЗ v3 — VITACONSULT_PUBLIC и т.д.)."""

    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
