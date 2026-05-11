"""Договор-оферта: текст, хэш версии, фиксация принятия (§13.4 ТЗ v3)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.models import User
from src.db.repos import log_event, log_pd_access

OFFER_VERSION = "2026-05-11-mvp"


def offer_hash() -> str:
    raw = f"{settings.offer_url}|{OFFER_VERSION}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def offer_summary() -> str:
    """Короткая сводка оферты для показа в чате до оплаты.

    Полный текст — у юриста, ссылка на сайт. Здесь — что входит, цена, возврат,
    реквизиты ИП.
    """
    return (
        "Договор-оферта (выжимка). Полный текст: "
        f"{settings.offer_url}\n\n"
        "Предмет: оказание услуги «Бизнес-чекап EDL OS» — аналитический "
        "отчёт + видео-разбор + майнд-карта оцифровки. Срок — 48 часов с "
        "момента оплаты.\n\n"
        "Цена: 9 000 ₽. Оплата через Robokassa (СБП/карта).\n\n"
        "Возврат: 100% в течение 14 дней с момента передачи материалов, "
        "если по итогам Чекапа вы не сможете внедрить ни одного из "
        "предложенных изменений.\n\n"
        "Исполнитель: ИП Жиганова Екатерина Викторовна, ИНН 027507994838. "
        f"Политика обработки ПД: {settings.privacy_policy_url}.\n\n"
        "Принятие оферты — отдельной кнопкой ниже. Без принятия оплата "
        "невозможна."
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
