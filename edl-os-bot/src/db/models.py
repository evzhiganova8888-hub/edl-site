"""SQLAlchemy models — БД схема из BOT_TZ_v3.md §15."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
    text as sql_text,
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
    # Mini-Чекап v2 fields
    quiz_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quiz_stage: Mapped[str | None] = mapped_column(Text)

    # Beta 12.05-19.05: подписка на e-mail отчёт «что мы сделали по ОС».
    wants_followup_report: Mapped[bool] = mapped_column(Boolean, default=False)
    # F4: виджет-источник
    source_channel: Mapped[str | None] = mapped_column(Text)
    widget_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # F6: воронка лида
    lead_stage: Mapped[str] = mapped_column(Text, default="cold")
    lead_stage_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    applications: Mapped[list[Application]] = relationship(back_populates="user")
    payments: Mapped[list[Payment]] = relationship(back_populates="user")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # inv_id заполняется через Postgres sequence `applications_inv_id_seq`
    # (создан в миграции 0002). `autoincrement=True` для не-PK колонок в
    # SQLAlchemy игнорируется, поэтому используем явный server_default,
    # чтобы SQLAlchemy не отправлял `inv_id=NULL` в INSERT.
    inv_id: Mapped[int] = mapped_column(
        BigInteger,
        server_default=sql_text("nextval('applications_inv_id_seq')"),
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
    checkup_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkup_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkup_pdf_url: Mapped[str | None] = mapped_column(Text)
    # F7: прогресс чекапа для паузы/возобновления
    checkup_current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    checkup_last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # F8: Plus видео-разбор
    plus_video_recommended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    plus_video_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    plus_video_url: Mapped[str | None] = mapped_column(Text)
    plus_video_sent_to_client_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class BotError(Base):
    """Bug-report от пользователя «⚠️ Ответ неверный» (§E.3 v3.1)."""

    __tablename__ = "bot_errors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    message_log_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("messages_log.id")
    )
    user_comment: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)
    prompt_patched: Mapped[bool] = mapped_column(Boolean, default=False)

    # Зеркало миграции 0004 — чтобы alembic --autogenerate не дрейфовал.
    __table_args__ = (
        Index(
            "idx_bot_errors_unresolved",
            "reported_at",
            postgresql_where=sql_text("reviewed_at IS NULL"),
        ),
        Index("idx_bot_errors_user", "user_id", "reported_at"),
    )


class Feedback(Base):
    """Структурированная обратная связь от пользователя (beta 12.05-19.05).

    В отличие от BotError (баги под конкретным ответом AI), Feedback — это
    «мне не хватает X / классно сделали Y / идея Z» на любом экране бота.
    """

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    # welcome / audit / quiz / offer / payment / ai_reply / refund / privacy / other
    step: Mapped[str] = mapped_column(Text, nullable=False)
    # bug / missing / idea / praise
    category: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "idx_feedback_unresolved",
            "reported_at",
            postgresql_where=sql_text("reviewed_at IS NULL"),
        ),
        Index("idx_feedback_step_category", "step", "category"),
    )


class AdminSession(Base):
    """Сессия in-bot admin доступа через access key (Task 3 v3.2)."""

    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    granted_by: Mapped[str] = mapped_column(Text)  # "static_env" | "access_key" | "{admin_tg_id}"
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CheckupAnswer(Base):
    """Ответы пользователя на 20 вопросов Чекапа (Task 5 v3.2)."""

    __tablename__ = "checkup_answers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    question_key: Mapped[str] = mapped_column(Text)
    layer: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer)
    quality_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_notes: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_checkup_answers_app", "application_id"),
        Index("uq_checkup_answers_app_q", "application_id", "question_key", unique=True),
    )


class QuizSubmission(Base):
    """Результат Mini-Чекапа v2 — из бота или с сайта (§11 ТЗ Mini-Чекап v2.0)."""

    __tablename__ = "quiz_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)  # 'bot' | 'site_page' | 'site_widget'
    widget_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    segment: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    stage_confidence: Mapped[str] = mapped_column(Text, default="high")
    outlier_flag: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    layer_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    growth_points: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consent_marketing_at_submit: Mapped[bool] = mapped_column(Boolean, default=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_quiz_submissions_user_id", "user_id"),
        Index("ix_quiz_submissions_widget_session_id", "widget_session_id"),
        Index("ix_quiz_submissions_created_at", "created_at"),
    )


class WidgetSession(Base):
    """Сессия виджета на сайте (F4)."""

    __tablename__ = "widget_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_channel: Mapped[str | None] = mapped_column(Text)
    page_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
