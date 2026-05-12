"""Memory / continuity (§I.4 ТЗ v3.1, опционально).

Когда пользователь возвращается через 24+ часа — подтягиваем сжатую
сводку его прошлых обращений (сегмент, под-профиль, последний intent,
оплаты, заявки), чтобы свободный диалог был контекстным без расспросов
заново. Полные сообщения НЕ грузим в context.user_data (велик размер) —
только сводку.

Источники:
- User: segment, sub_profile, stage, email, company_name, quiz_score
- Application: type/status/created_at последних 3
- Payment: succeeded count, last paid_at
- MessageLog: 5 последних inbound text (обрезанных до 200 символов)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.pd_sanitize import sanitize
from src.db.models import Application, MessageLog, Payment, User

_GAP_FOR_RECAP = timedelta(hours=24)


async def build_user_recap(
    session: AsyncSession, user: User, *, now: datetime | None = None
) -> dict[str, Any] | None:
    """Возвращает сводку, если пользователь возвращается через 24+ ч.

    None — если пользователь свежий или активен только что (recap не нужен).
    """
    now = now or datetime.now(timezone.utc)
    last_msg = (
        await session.execute(
            select(MessageLog)
            .where(MessageLog.user_id == user.id)
            .order_by(MessageLog.occurred_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if last_msg is None:
        return None
    gap = now - last_msg.occurred_at
    if gap < _GAP_FOR_RECAP:
        return None

    # Последние 5 inbound
    recent = (
        (
            await session.execute(
                select(MessageLog)
                .where(MessageLog.user_id == user.id)
                .where(MessageLog.direction == "inbound")
                .order_by(MessageLog.occurred_at.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )

    # Последние 3 заявки
    apps = (
        (
            await session.execute(
                select(Application)
                .where(Application.user_id == user.id)
                .order_by(Application.created_at.desc())
                .limit(3)
            )
        )
        .scalars()
        .all()
    )

    # Оплаты — только succeeded
    pay_count = await session.scalar(
        select(Payment)
        .where(Payment.user_id == user.id)
        .where(Payment.status == "succeeded")
    )

    return {
        "gap_hours": int(gap.total_seconds() // 3600),
        "segment": user.segment,
        "sub_profile": user.sub_profile,
        "stage": user.stage,
        "company_name": user.company_name,
        "quiz_score": user.quiz_score,
        # CRITICAL: previews идут в system prompt → Anthropic API. Применяем
        # sanitize_pd ДО включения, чтобы email/телефон/ИНН/секреты не утекали
        # за рубеж (152-ФЗ). См. P0-1 в docs/threat_model.md.
        "recent_inbound": [
            {
                "at": m.occurred_at.isoformat() if m.occurred_at else None,
                "preview": sanitize((m.text or "")[:200]),
                "intent": m.intent_detected,
            }
            for m in recent
        ],
        "applications": [
            {
                "type": a.type,
                "status": a.status,
                "source": a.source,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in apps
        ],
        "had_succeeded_payment": pay_count is not None,
    }


def recap_to_prompt_snippet(recap: dict[str, Any]) -> str:
    """Превращаем recap в короткий блок для system-промпта.

    Намеренно компактно: <300 токенов. Сюда НЕ кладём ПД — recap уже
    собран по обезличенному превью inbound (нет email, телефонов).
    """
    if not recap:
        return ""
    parts: list[str] = []
    parts.append(
        f"## Контекст из прошлых обращений (последняя активность {recap['gap_hours']} ч назад)"
    )
    if recap.get("segment"):
        seg = recap["segment"]
        if recap.get("sub_profile"):
            seg += f" ({recap['sub_profile']})"
        parts.append(f"Сегмент: {seg}. Стадия: {recap.get('stage', 'cold')}.")
    if recap.get("quiz_score") is not None:
        parts.append(f"Quiz Founder OS Score: {recap['quiz_score']}/100.")
    if recap.get("had_succeeded_payment"):
        parts.append("Уже оплачивал(а) Чекап ранее.")
    apps = recap.get("applications") or []
    if apps:
        parts.append("Последние заявки:")
        for a in apps:
            parts.append(f"  - {a['type']}: {a['status']} ({a['source']})")
    msgs = recap.get("recent_inbound") or []
    if msgs:
        parts.append("Последние сообщения (для контекста, не повторять):")
        for m in msgs[:3]:  # показываем максимум 3
            parts.append(f"  - «{m['preview']}»")
    parts.append(
        "Не задавай вопросов, на которые ответ уже есть в этом контексте. "
        "При первой реплике — упомяни, что помнишь предыдущий разговор."
    )
    return "\n".join(parts)
