"""F8: Celery-задача: брифинг Кате через 24ч после оплаты Plus-плана.

Flow:
1. YooKassa webhook → payment.succeeded → schedule_plus_video_brief.delay(app_id)
2. 24ч → send_plus_video_brief_to_katya(app_id)
3. Катя пишет /upload_plus_video <app_id> и прикладывает видео
4. Бот отправляет видео клиенту
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_VIDEO_RECS_TEMPLATE = """📋 Структура видео-разбора (15 мин по ТЗ §7.1):

0:00–2:00 · Контекст бизнеса — сегмент, стадия, типичный кризис.
2:00–7:00 · 3 ключевые точки разбора — что они означают в ощущениях, не в цифрах.
7:00–11:00 · Что бы сделали на их месте — 3 шага на 90 дней.
11:00–14:00 · Hook на Диагностику — что нельзя увидеть в Чекапе, видно в Диагностике.
14:00–15:00 · 14-дневная гарантия + Иван @lvanKhudyakov для Диагностики.

ТОН: медицинский диагноз, не маркетинг.
ЗАПРЕЩЕНО: «окупается», «революционн», «купите», «обязательно возьмите».
"""


def _build_cheat_sheet(answers: list) -> str:
    """Авто-шпаргалка по 3 самым «цифровым» ответам клиента.

    Эвристика: берём ответы с цифрами, по одному из каждого слоя
    (приоритет — money / operations / strategy / funnel). Это часто
    самые продаваемые акценты для видео — конкретные числа клиента.
    """
    by_layer: dict[str, list] = {}
    for a in answers:
        text = (a.text or "").strip()
        if not text:
            continue
        if getattr(a, "is_decline", False):
            continue
        has_digit = any(c.isdigit() for c in text)
        if not has_digit:
            continue
        by_layer.setdefault(a.layer or "other", []).append(a)

    # Приоритет слоёв для видео — финансы и операционка обычно самые
    # дорогие в плане потерь
    priority = ("money", "operations", "strategy", "funnel", "finance", "sales", "other")
    snippets: list[str] = []
    for layer in priority:
        bucket = by_layer.get(layer, [])
        if not bucket:
            continue
        # Берём самый длинный ответ в слое — обычно самый содержательный
        best = max(bucket, key=lambda a: len(a.text or ""))
        text = (best.text or "")[:240].rstrip()
        if len(best.text or "") > 240:
            text += "…"
        snippets.append(f"• [{layer.upper()}] {text}")
        if len(snippets) >= 3:
            break

    if not snippets:
        return "💬 Цифровых ответов не найдено — смотрите PDF целиком."

    return "💬 ТОП-3 ответа клиента с цифрами (для прямых цитат в видео):\n" + "\n\n".join(snippets)


@celery_app.task(name="src.tasks.notify_plus_video.schedule_plus_video_brief")
def schedule_plus_video_brief(application_id: str) -> None:
    """Планирует отправку брифа Кате через 24 часа."""
    eta = datetime.now(timezone.utc) + timedelta(hours=24)
    send_plus_video_brief_to_katya.apply_async(args=[application_id], eta=eta)
    logger.info("Plus video brief scheduled for application %s at %s", application_id, eta)


@celery_app.task(name="src.tasks.notify_plus_video.send_plus_video_brief_to_katya")
def send_plus_video_brief_to_katya(application_id: str) -> None:
    """Отправляет Кате брифинг с PDF-отчётом и рекомендациями по видео."""
    import asyncio

    asyncio.run(_async_send_brief(application_id))


async def _async_send_brief(application_id: str) -> None:
    import telegram
    from sqlalchemy import select

    from src.core.config import settings
    from src.db.models import Application, CheckupAnswer, User
    from src.db.session import async_session_factory

    factory = async_session_factory()
    async with factory() as session:
        from uuid import UUID
        try:
            app_uuid = UUID(application_id)
        except ValueError:
            logger.error("Invalid application_id: %s", application_id)
            return

        app = await session.get(Application, app_uuid)
        if app is None:
            logger.error("Application %s not found", application_id)
            return

        user = (await session.execute(
            select(User).where(User.id == app.user_id)
        )).scalar_one_or_none()
        if user is None:
            return

        answers = (await session.execute(
            select(CheckupAnswer).where(CheckupAnswer.application_id == app_uuid)
        )).scalars().all()

        # Обновляем флаг отправки брифа
        if hasattr(app, "plus_video_recommended_at"):
            app.plus_video_recommended_at = __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            )
        await session.commit()

    pdf_url = app.checkup_pdf_url or "—"
    email = user.email or "—"
    answers_count = len(answers)
    archetype = getattr(app, "archetype", None) or "—"
    cheat_sheet = _build_cheat_sheet(answers)

    text = (
        f"🎬 Plus-видео для клиента\n\n"
        f"Application: {application_id}\n"
        f"Email: {email}\n"
        f"Сегмент × стадия: {user.segment or '—'} × {user.stage or '—'} (архетип: {archetype})\n"
        f"Ответов в чекапе: {answers_count}/20\n"
        f"PDF-отчёт: {pdf_url}\n\n"
        f"{cheat_sheet}\n\n"
        f"{_VIDEO_RECS_TEMPLATE}\n"
        f"Когда запишете — используйте:\n"
        f"/upload_plus_video {application_id}"
    )

    if settings.admin_chat_id and settings.bot_token:
        bot = telegram.Bot(token=settings.bot_token)
        async with bot:
            await bot.send_message(chat_id=settings.admin_chat_id, text=text)
            logger.info("Plus video brief sent for application %s", application_id)
