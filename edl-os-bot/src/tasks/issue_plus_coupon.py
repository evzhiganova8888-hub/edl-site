"""Авто-выдача купона −20% Plus-клиенту через 24ч после видео-разбора.

Триггер: в момент отправки Plus-видео клиенту (`upload_plus_video_command`)
планируется этот task с `countdown=86400` (24ч). По истечении выдаём
купон через `coupon_engine.issue_coupon` (idempotent — повторный вызов
не создаёт второй купон).

ТЗ §4.7 + §8: купон активен 24 часа от выдачи, цена с купоном 36 000 ₽
(скидка 20% от 45 000 ₽ за Диагностику).
"""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="src.tasks.issue_plus_coupon.schedule_plus_coupon")
def schedule_plus_coupon(application_id: str) -> bool:
    """Выдаёт купон Plus-клиенту и шлёт ему сообщение с кодом.

    Возвращает True если купон выдан/уже существовал, False при ошибке.
    """
    return asyncio.run(_run(application_id))


async def _run(application_id: str) -> bool:
    from src.core import coupon_engine as ce
    from src.core.config import settings
    from src.db.models import Application, User
    from src.db.session import async_session_factory

    try:
        app_uuid = UUID(application_id)
    except ValueError:
        logger.error("Bad application_id: %s", application_id)
        return False

    factory = async_session_factory()
    async with factory() as session:
        app = await session.get(Application, app_uuid)
        if app is None:
            logger.warning("Application %s not found, skipping coupon", application_id)
            return False
        if (app.payload or {}).get("plan") != "plus":
            logger.info("App %s is not Plus, skipping coupon", application_id)
            return False
        user = await session.get(User, app.user_id)
        if user is None:
            return False

        coupon = await ce.issue_coupon(session, user_id=user.id, application_id=app_uuid)
        await session.commit()

    # Уведомление клиенту
    try:
        from src.main import _ptb_app  # type: ignore[attr-defined]
        if _ptb_app is None:
            logger.warning("PTB app not available, coupon issued but not delivered")
            return True

        deadline = coupon.expires_at.strftime("%d.%m.%Y %H:%M UTC")
        await _ptb_app.bot.send_message(
            chat_id=user.telegram_id,
            text=(
                f"Прошло 2 дня с момента, как вы получили PDF. Если разбор и "
                f"видео были полезны — есть один практический шаг дальше.\n\n"
                f"📋 *Диагностика · следующий уровень погружения*\n\n"
                f"Что это: подключение к вашим источникам (1С / CRM / банк) "
                f"в режиме read-only. Дашборд L1–L3 в реальных цифрах. "
                f"Live-демо 3 настроенных под вас агентов. 90-дневный план.\n\n"
                f"Срок: 2 недели. Полная цена: 45 000 ₽.\n\n"
                f"Для вас как клиента Чекапа Plus — *купон −20%*:\n\n"
                f"🎟 Промокод: `{coupon.code}`\n"
                f"Цена с купоном: *36 000 ₽*\n"
                f"Купон действует: 24 часа от этого сообщения "
                f"(до {deadline})\n\n"
                f"Активировать: /diagnostika в боте\n"
                f"Или написать Ивану напрямую: @{settings.sales_username}\n\n"
                f"Если сейчас не время — это нормально. Все материалы Чекапа "
                f"остаются у вас. Запись на Диагностику в любой момент по "
                f"полной цене.\n\n"
                f"— команда EDL OS"
            ),
            parse_mode="Markdown",
        )
        logger.info("Plus coupon delivered to user %s code=%s", user.telegram_id, coupon.code)
        return True
    except Exception:
        logger.exception("Failed to deliver plus coupon to user")
        return True  # купон выдан, не доставлен — алерт через celery logs
