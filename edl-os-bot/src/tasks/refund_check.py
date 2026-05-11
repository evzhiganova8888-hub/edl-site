"""14-дневный refund timer (§6.1, §10 ТЗ v3).

Когда `refund_eligible_until` истекает — закрываем окно возврата
(переводим в `delivered` и логируем). Запускается раз в час через beat.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Application, Event
from src.db.session import async_session_factory
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="src.tasks.refund_check.expire_refund_window")
def expire_refund_window() -> int:
    """Закрывает окна возврата у заявок, у которых refund_eligible_until прошёл.

    Возвращает количество обработанных заявок.
    """
    return asyncio.run(_expire_async())


async def _expire_async() -> int:
    factory = async_session_factory()
    now = datetime.now(timezone.utc)
    count = 0
    async with factory() as session:
        stmt = (
            select(Application)
            .where(Application.refund_eligible_until.is_not(None))
            .where(Application.refund_eligible_until < now)
            .where(Application.status == "paid")
        )
        result = await session.execute(stmt)
        for app in result.scalars():
            app.status = "delivered"
            app.delivered_at = now
            session.add(
                Event(
                    user_id=app.user_id,
                    event="refund_window_expired",
                    payload={"application_id": str(app.id)},
                )
            )
            count += 1
        await session.commit()
    if count:
        logger.info("Expired refund window for %d applications", count)
    return count
