"""152-ФЗ — получение и проверка согласия на обработку ПД (§9, §13)."""
from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.models import User
from src.db.repos import log_event, log_pd_access, record_consent_pd


def policy_hash() -> str:
    """Хэш версии политики — пишется вместе с consent_pd_given_at."""
    raw = f"{settings.privacy_policy_url}|{settings.privacy_policy_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def consent_text() -> str:
    """Минимальный текст согласия по BOT_TZ §7.1."""
    return (
        "Прежде чем продолжить, мне нужно ваше согласие на обработку "
        "персональных данных (ФИО, e-mail, телефон, сведения о бизнесе, "
        "которые вы сами сообщите).\n\n"
        "Цели обработки:\n"
        "• оказание услуг EDL OS (демо, чекап, диагностика, спринт)\n"
        "• связь с вами по этим услугам\n"
        "• выставление счетов и формирование чеков\n\n"
        "Срок хранения: до отзыва согласия или 3 года с последней активности.\n\n"
        "Оператор: ИП Жиганова Екатерина Викторовна, ИНН 027507994838.\n"
        f"Политика: {settings.privacy_policy_url}"
    )


def has_consent(user: User) -> bool:
    return user.consent_pd_given_at is not None


async def give_consent(session: AsyncSession, user: User) -> None:
    await record_consent_pd(session, user, version=policy_hash())
    await log_event(
        session,
        user_id=user.id,
        event="consent_pd_given",
        payload={"version": policy_hash()},
    )
    await log_pd_access(
        session,
        actor="system",
        user_id=user.id,
        action="update",
        fields=["consent_pd_given_at", "consent_pd_version"],
    )
