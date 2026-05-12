"""Договор-оферта: текст, хэш версии, фиксация принятия (§13.4 ТЗ v3)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.models import User
from src.db.repos import log_event, log_pd_access

OFFER_VERSION = "2026-05"


def offer_hash() -> str:
    raw = f"{settings.offer_url}|{OFFER_VERSION}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def offer_summary() -> str:
    """Короткая сводка оферты для показа в чате до оплаты.

    Должна соответствовать boilerplate в legal/offer.html (Май 2026).
    Полный текст — на сайте, ссылка ниже.
    """
    # В manual-режиме (Май 2026) оплата идёт через счёт от Ивана, не Robokassa.
    payment_line = (
        "Оплата по счёту от ИП через расчётный счёт (СБП / банк. перевод). "
        "Иван оформит счёт после принятия оферты."
        if settings.payment_mode == "manual"
        else "Оплата через Robokassa (СБП / карта)."
    )
    return (
        "Договор-оферта (выжимка). Полный текст: "
        f"{settings.offer_url}\n\n"
        "Предмет: услуга «Бизнес-чекап EDL OS» — диагностика операционной "
        "модели по 4 слоям (Стратегия, Воронка, Операционка, Деньги).\n\n"
        "Два тарифа:\n"
        "• Базовый — 9 000 ₽, 48 часов с момента проведения интервью.\n"
        "• Plus — 14 000 ₽, 7 рабочих дней (с видео-разбором от Кати).\n\n"
        f"{payment_line}\n\n"
        "Возврат 100%: безусловно в течение 14 календарных дней с момента "
        "передачи материалов. Причину указывать не нужно — один клик /refund.\n\n"
        "Исполнитель: ИП Жиганова Екатерина Викторовна\n"
        "ИНН 027507994838 · ОГРНИП 325028000082251 · УСН (без НДС).\n"
        f"Политика обработки ПД: {settings.privacy_policy_url}\n\n"
        "Принимая оферту, вы соглашаетесь со всеми её условиями. Без принятия "
        "оплата невозможна."
    )


def is_offer_accepted(user: User) -> bool:
    return user.consent_offer_accepted_at is not None


async def accept_offer(session: AsyncSession, user: User) -> None:
    user.consent_offer_accepted_at = datetime.now(timezone.utc)
    await log_event(
        session,
        user_id=user.id,
        event="offer_accepted",
        payload={"version": OFFER_VERSION, "hash": offer_hash()},
    )
    await log_pd_access(
        session,
        actor="system",
        user_id=user.id,
        action="update",
        fields=["consent_offer_accepted_at"],
    )
