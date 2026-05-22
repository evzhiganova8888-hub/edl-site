"""Fail-safe «5 минут без ответа» (ТЗ §3.6 + AC4 critical).

Каждую минуту celery beat сканирует applications, у которых:
- Чекап в работе (status=paid, checkup_completed_at IS NULL);
- checkup_current_question_index > 0 (клиент стартовал);
- checkup_last_active_at < now − 5min (клиент молчит 5 мин);
- spin_failsafe_warning_sent_at IS NULL (мы ещё не предупреждали).

Отправляет сообщение «Заметила, что прошло 5 минут…» и помечает
spin_failsafe_warning_sent_at = NOW. После следующего ответа FSM сбрасывает
эту колонку обратно в NULL (если она будет уже не нужна для следующего вопроса).

В этой реализации сброс на каждый ответ не делается — клиент получает
fail-safe максимум один раз за весь Чекап. Это сознательный trade-off:
не назойливо, но при этом ловим самый частый случай (фаундер открыл
вопрос, переключился, забыл).
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

FAILSAFE_THRESHOLD = timedelta(minutes=5)


@celery_app.task(name="src.tasks.checkup_failsafe.run_failsafe_scan")
def run_failsafe_scan() -> int:
    """Возвращает количество отправленных fail-safe сообщений."""
    return asyncio.run(_scan_async())


async def _scan_async() -> int:
    factory = async_session_factory()
    now = datetime.now(timezone.utc)
    cutoff = now - FAILSAFE_THRESHOLD
    sent = 0

    async with factory() as session:
        stmt = (
            select(Application, User)
            .join(User, Application.user_id == User.id)
            .where(Application.type == "audit")
            .where(Application.status == "paid")
            .where(Application.checkup_completed_at.is_(None))
            .where(Application.checkup_current_question_index > 0)
            .where(Application.checkup_last_active_at.is_not(None))
            .where(Application.checkup_last_active_at < cutoff)
            .where(Application.spin_failsafe_warning_sent_at.is_(None))
        )
        rows = (await session.execute(stmt)).all()

        for app, user in rows:
            try:
                await _send_failsafe(user.telegram_id, app.checkup_current_question_index)
                app.spin_failsafe_warning_sent_at = now
                sent += 1
                logger.info(
                    "checkup_failsafe.sent app=%s q_idx=%d minutes_silent=%d",
                    app.id,
                    app.checkup_current_question_index,
                    int((now - app.checkup_last_active_at).total_seconds() // 60),
                )
            except Exception:
                logger.exception(
                    "checkup_failsafe.send_failed app=%s telegram_id=%s",
                    app.id,
                    user.telegram_id,
                )

        await session.commit()

    return sent


async def _send_failsafe(telegram_id: int, q_idx: int) -> None:
    from src.main import _ptb_app  # type: ignore[attr-defined]
    if _ptb_app is None:
        return
    await _ptb_app.bot.send_message(
        chat_id=telegram_id,
        text=(
            f"Заметили, что прошло 5 минут на вопросе {q_idx}/16. "
            f"Это нормально — некоторые вопросы требуют посмотреть в 1С / "
            f"CRM / банке.\n\n"
            f"Если нужно больше времени — напишите «пауза», прогресс сохранится "
            f"и вернёмся когда удобно (команда /checkup). Если ещё пишете "
            f"ответ — просто отправьте его."
        ),
    )
