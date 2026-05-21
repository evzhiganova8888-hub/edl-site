"""Celery-task: помечать просроченные active-купоны 'expired'.

Не критичен для корректности — `coupon_engine` делает двойную проверку по
времени на каждом клиентском пути. Полезен для аналитики и чтобы
admin-команды показывали актуальный статус без вычислений.

Запускается раз в 15 минут через beat (см. `celery_app.py`).
"""
from __future__ import annotations

import asyncio
import logging

from src.core.coupon_engine import expire_overdue_coupons
from src.db.session import async_session_factory
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="src.tasks.expire_coupons.run_expire_coupons")
def run_expire_coupons() -> int:
    """Возвращает число купонов, переведённых в status='expired'."""
    return asyncio.run(_expire_async())


async def _expire_async() -> int:
    factory = async_session_factory()
    async with factory() as session:
        n = await expire_overdue_coupons(session)
        await session.commit()
    if n:
        logger.info("expire_coupons.tick n=%d", n)
    return n
