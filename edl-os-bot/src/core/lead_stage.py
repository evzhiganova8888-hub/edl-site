"""F6: Логика расчёта и обновления lead_stage (cold/warm/hot/client).

Уровень 3: полная адаптация тона бота в зависимости от стадии лида.
Вызывается из dialog.handle_text перед каждым LLM-ответом.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Application, Event, User

logger = logging.getLogger(__name__)

LEAD_STAGES = ["cold", "warm", "hot", "client"]

# События, которые переводят лида в warm
_WARM_EVENTS = frozenset([
    "quiz_completed",
    "segment_determined",
    "pricing_asked",
    "methodology_asked",
    "guarantee_asked",
    "audit_intro_shown",
])

# События, которые переводят лида в hot
_HOT_EVENTS = frozenset([
    "audit_purchase_started",
    "email_provided",
    "invoice_requested",
    "manual_payment_submitted",
    "calendly_slot_booked",
])

# Если в hot больше 7 дней без оплаты — возвращаем в warm
_HOT_COOLDOWN_DAYS = 7


async def calculate_lead_stage(user: User, session: AsyncSession) -> str:
    """Вычисляет актуальную стадию лида по данным в БД."""

    # Client: есть оплаченная заявка
    paid = (await session.execute(
        select(Application).where(
            Application.user_id == user.id,
            Application.status == "paid",
        ).limit(1)
    )).scalar_one_or_none()
    if paid:
        return "client"

    # Hot: есть hot-событие
    hot_event = (await session.execute(
        select(Event).where(
            Event.user_id == user.id,
            Event.event.in_(_HOT_EVENTS),
        ).limit(1)
    )).scalar_one_or_none()

    if hot_event:
        # Cooldown: если в hot > 7 дней без оплаты → warm
        stage_ts = getattr(user, "lead_stage_updated_at", None)
        if (
            getattr(user, "lead_stage", None) == "hot"
            and stage_ts is not None
        ):
            days_in_hot = (datetime.now(timezone.utc) - stage_ts).days
            if days_in_hot > _HOT_COOLDOWN_DAYS:
                return "warm"
        return "hot"

    # Warm: есть warm-событие
    warm_event = (await session.execute(
        select(Event).where(
            Event.user_id == user.id,
            Event.event.in_(_WARM_EVENTS),
        ).limit(1)
    )).scalar_one_or_none()

    if warm_event:
        return "warm"

    return "cold"


async def update_lead_stage(user: User, session: AsyncSession) -> str:
    """Пересчитывает и сохраняет lead_stage если изменился. Возвращает новую стадию."""
    new_stage = await calculate_lead_stage(user, session)

    current = getattr(user, "lead_stage", None) or user.stage or "cold"
    if new_stage != current:
        old_stage = current
        # Обновляем оба поля для обратной совместимости
        if hasattr(user, "lead_stage"):
            user.lead_stage = new_stage
        if hasattr(user, "lead_stage_updated_at"):
            user.lead_stage_updated_at = datetime.now(timezone.utc)
        user.stage = new_stage  # синхронизируем старое поле

        logger.info(
            "lead_stage changed for user %s: %s → %s", user.id, old_stage, new_stage
        )

        # Audit event (не через log_event чтобы избежать рекурсии)
        from src.db.models import Event as EventModel
        session.add(EventModel(
            user_id=user.id,
            event="lead_stage_changed",
            payload={"from": old_stage, "to": new_stage},
        ))

    return new_stage
