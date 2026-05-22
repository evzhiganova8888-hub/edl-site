"""Detect dormant Чекапы и предлагать клиенту начать заново.

ТЗ §3.6 + EC2:
- Если 14 дней молчания после начала Чекапа — мягкое напоминание в TG.
- Если 30 дней молчания — помечается как dormant. При возврате клиент
  получает выбор «Начать заново» / «Продолжить» (Q3 UX-разрыв ТЗ).

Запускается раз в день в 11:00 МСК через celery beat. Идемпотентен:
если напоминание уже отправлено, не отправляет повторно — для этого
ведём колонку `applications.payload.dormant_notice_sent_at`.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.db.models import Application, User
from src.db.session import async_session_factory
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

SOFT_REMINDER_DAYS = 14
DORMANT_DAYS = 30


@celery_app.task(name="src.tasks.dormant_checkup.run_dormant_scan")
def run_dormant_scan() -> dict[str, int]:
    """Возвращает {soft_sent, dormant_marked}."""
    return asyncio.run(_scan_async())


async def _scan_async() -> dict[str, int]:
    factory = async_session_factory()
    now = datetime.now(timezone.utc)
    soft_sent = 0
    dormant_marked = 0

    async with factory() as session:
        # Кандидаты: paid Application с checkup в работе, не завершённый,
        # последняя активность давно. Q_idx > 0 — клиент уже стартовал.
        stmt = (
            select(Application, User)
            .join(User, Application.user_id == User.id)
            .where(Application.type == "audit")
            .where(Application.status == "paid")
            .where(Application.checkup_completed_at.is_(None))
            .where(Application.checkup_current_question_index > 0)
            .where(Application.checkup_last_active_at.is_not(None))
        )
        rows = (await session.execute(stmt)).all()

        for app, user in rows:
            last_active = app.checkup_last_active_at
            if last_active is None:
                continue
            days_silent = (now - last_active).days
            payload = dict(app.payload or {})

            if days_silent >= DORMANT_DAYS and payload.get("dormant_marked_at") is None:
                payload["dormant_marked_at"] = now.isoformat()
                payload["dormant_days_at_marking"] = days_silent
                app.payload = payload
                dormant_marked += 1
                logger.info(
                    "dormant_checkup.marked app=%s days_silent=%d",
                    app.id,
                    days_silent,
                )
                # Сообщение клиенту — best effort
                await _notify_user_dormant(user.telegram_id, app.checkup_current_question_index)
            elif (
                SOFT_REMINDER_DAYS <= days_silent < DORMANT_DAYS
                and payload.get("dormant_soft_notice_sent_at") is None
            ):
                payload["dormant_soft_notice_sent_at"] = now.isoformat()
                app.payload = payload
                soft_sent += 1
                logger.info(
                    "dormant_checkup.soft_notice app=%s days_silent=%d",
                    app.id,
                    days_silent,
                )
                await _notify_user_soft(user.telegram_id, app.checkup_current_question_index)

        await session.commit()

    return {"soft_sent": soft_sent, "dormant_marked": dormant_marked}


async def _notify_user_soft(telegram_id: int, q_idx: int) -> None:
    """Мягкое напоминание через 14 дней."""
    try:
        from src.main import _ptb_app  # type: ignore[attr-defined]
        if _ptb_app is None:
            return
        await _ptb_app.bot.send_message(
            chat_id=telegram_id,
            text=(
                f"Чекап ждёт вас — вы остановились на вопросе {q_idx}/16, "
                f"прошло 14 дней.\n\n"
                f"Прогресс сохранён. Команда /checkup — продолжить с того места."
            ),
        )
    except Exception:
        logger.exception("Failed to send soft dormant notice to %s", telegram_id)


async def _notify_user_dormant(telegram_id: int, q_idx: int) -> None:
    """30 дней молчания — предлагаем начать заново."""
    try:
        from src.main import _ptb_app  # type: ignore[attr-defined]
        if _ptb_app is None:
            return
        await _ptb_app.bot.send_message(
            chat_id=telegram_id,
            text=(
                f"Чекап у вас 30+ дней без активности — прогресс ({q_idx}/16) "
                f"всё ещё сохранён, но за такой срок контекст меняется. "
                f"Когда вернётесь, /checkup предложит выбор: продолжить с "
                f"того места или начать заново со свежими ответами."
            ),
        )
    except Exception:
        logger.exception("Failed to send dormant notice to %s", telegram_id)
