"""Entry point — FastAPI + python-telegram-bot.

Поддерживает 2 режима:
- polling (по умолчанию, для локальной разработки)
- webhook (если задан WEBHOOK_BASE_URL — для продакшена)

HTTP endpoints:
- GET  /health — liveness
- POST /webhook — Telegram updates
- POST /webhook/yookassa — YooKassa payment events (F1)
- POST /widget/message — веб-виджет входящее сообщение (F4)
- GET  /widget/stream/{session_id} — SSE ответы бота в виджет (F4)

Запуск: `python -m src.main`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from fastapi.middleware.cors import CORSMiddleware

from src.admin.routes import router as admin_router
from src.api.quiz import router as quiz_router
from src.bot.handlers import register
from src.core.config import settings

# F11: Sentry SDK — инициализируем до basicConfig чтобы поймать все ошибки
_sentry_dsn = os.getenv("SENTRY_DSN", "")
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "production"),
        )
    except ImportError:
        pass  # sentry-sdk не установлен — не блокирует запуск

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# httpx и httpcore логируют каждый исходящий HTTP запрос с полным URL на INFO
# уровне. Для Telegram Bot API это значит, что в логах оказывается строка вида
# `POST https://api.telegram.org/bot<TOKEN>/sendMessage` — BOT_TOKEN утекает в
# Railway logs. Любой, кто получит доступ к логам (или скриншот логов в чате),
# получит токен и может подделать сообщения от имени бота.
# Поднимаем уровень до WARNING — нам всё равно нужны только проблемы, не каждый
# 200 OK от Telegram.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def build_application() -> Application:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not set — fill .env and try again")
    builder = ApplicationBuilder().token(settings.bot_token)
    app = builder.build()
    register(app)
    return app


_ptb_app: Application | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _ptb_app
    _ptb_app = build_application()

    await _ptb_app.initialize()
    await _ptb_app.start()

    if settings.use_webhook:
        webhook_url = f"{settings.webhook_base_url.rstrip('/')}/webhook"
        await _ptb_app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret_token or None,
            drop_pending_updates=True,
        )
        logger.info("Starting in WEBHOOK mode. URL=%s", webhook_url)
    else:
        asyncio.create_task(_run_polling(_ptb_app))
        if settings.environment == "production":
            logger.warning(
                "Starting in POLLING mode in production — Railway deployments will "
                "cause 409 Conflict (two instances polling at once) and the user "
                "may see 'menu + error' duplicate replies. Set WEBHOOK_BASE_URL to "
                "switch to webhook mode. See docs/qa_audit_2026-05-17/RAILWAY_WEBHOOK_SETUP.md"
            )
        else:
            logger.info("Starting in POLLING mode (development)")

    try:
        yield
    finally:
        # Не вызываем delete_webhook(): на Railway rolling deploy старый
        # контейнер получает SIGTERM ПОСЛЕ того как новый уже сделал
        # set_webhook → старый стирает URL → Telegram перестаёт слать
        # апдейты → бот молчит до следующего set_webhook. set_webhook
        # идемпотентен; новый контейнер сам перезапишет URL при старте.
        # Если бот выводится из эксплуатации навсегда — webhook удалит
        # @BotFather / setWebhook вручную, а не lifecycle.
        await _ptb_app.stop()
        await _ptb_app.shutdown()


async def _run_polling(app: Application) -> None:
    try:
        await app.updater.start_polling(drop_pending_updates=True)
    except Exception:
        logger.exception("polling failed")


api = FastAPI(title="EDL OS Bot", version="0.4.0", lifespan=lifespan)
api.include_router(admin_router)
api.include_router(quiz_router)

# CORS для публичного API Mini-Чекапа (сайт → бот-сервер)
api.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://elephantdreams.ru",
        "https://www.elephantdreams.ru",
        "http://localhost:5500",   # локальная разработка
        "http://127.0.0.1:5500",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Internal-Token"],
    max_age=3600,
)


@api.middleware("http")
async def _log_requests(request: Request, call_next):
    """Лог каждого входящего HTTP-запроса. Нужен для диагностики Railway
    proxy 502 — без него видно только uvicorn-логи, по которым нельзя
    отличить «запрос не дошёл» от «запрос дошёл и упал»."""
    response = await call_next(request)
    logger.info(
        "HTTP %s %s -> %d", request.method, request.url.path, response.status_code
    )
    return response


@api.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "use_webhook": settings.use_webhook,
        "payment_mode": settings.payment_mode,
    }


@api.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Telegram webhook receiver.

    Кладёт update в `_ptb_app.update_queue` и сразу отвечает 200 OK.
    Обработку handlers'ом делает фоновая таска `_update_fetcher`, которую
    запустил `Application.start()`.

    Почему не `await process_update(update)`:
    1) Telegram ставит таймаут на POST /webhook ~30 сек; если handler
       делает LLM-вызов (Claude Haiku 5–15 сек) или медленный DB-запрос,
       Railway proxy успевает закрыть соединение по таймауту → 502 Bad
       Gateway → Telegram повторяет тот же update до 24 часов.
    2) В polling mode update тоже идёт через `update_queue` → одинаковый
       processing-path для обоих режимов.
    """
    if (
        settings.webhook_secret_token
        and x_telegram_bot_api_secret_token != settings.webhook_secret_token
    ):
        raise HTTPException(status_code=401, detail="Invalid secret token")
    if _ptb_app is None:
        raise HTTPException(status_code=503, detail="Bot is not ready")
    data = await request.json()
    update = Update.de_json(data, _ptb_app.bot)
    await _ptb_app.update_queue.put(update)
    return {"ok": True}


@api.post("/webhook/yookassa")
async def yookassa_webhook(request: Request) -> dict:
    """F1: YooKassa payment events webhook.

    Принимает payment.succeeded / payment.canceled / refund.succeeded.
    Для payment.succeeded — помечает заявку как оплаченную через
    mark_application_paid (idempotent).
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = body.get("event", "")
    obj = body.get("object", {})
    payment_id = obj.get("id")
    metadata = obj.get("metadata", {})

    logger.info("YooKassa webhook: event=%s payment_id=%s", event_type, payment_id)

    if event_type == "payment.succeeded":
        application_id = metadata.get("application_id") or metadata.get("inv_id")
        if not application_id:
            logger.error("YooKassa webhook: no application_id in metadata: %s", metadata)
            return {"status": "ok"}

        amount_str = obj.get("amount", {}).get("value", "0")
        try:
            amount_rub = float(amount_str)
        except ValueError:
            amount_rub = 0.0

        from src.core.payment_marking import find_application_by_id, mark_application_paid
        from src.db.models import User
        from src.db.session import async_session_factory
        from sqlalchemy import select

        factory = async_session_factory()
        async with factory() as session:
            app = await find_application_by_id(session, application_id)
            if app is None:
                logger.error("YooKassa webhook: application %s not found", application_id)
                return {"status": "ok"}
            user = (await session.execute(
                select(User).where(User.id == app.user_id)
            )).scalar_one_or_none()
            if user is None:
                logger.error("YooKassa webhook: user not found for application %s", application_id)
                return {"status": "ok"}

            result = await mark_application_paid(
                session,
                app=app,
                user=user,
                amount_rub=amount_rub,
                payment_provider="yookassa",
                provider_payment_id=payment_id,
                actor="yookassa_webhook",
            )
            await session.commit()

        if not result.get("already_paid"):
            # SoT v1.5 patch §2.3 шаг 2: видео-бриф Кате триггерится от
            # ЗАВЕРШЕНИЯ Чекапа (checkup_handlers._do_complete), не от оплаты.
            # Это решает кейс «клиент оплатил, но не прошёл Чекап неделю» —
            # раньше Катя получала бесполезный бриф через 24ч.
            pass

            # Уведомить пользователя через бот
            if _ptb_app and user.telegram_id:
                try:
                    await _ptb_app.bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            "✅ Оплата получена! Спасибо.\n\n"
                            "Доступ к Чекапу открыт. Введите /checkup чтобы начать."
                        ),
                    )
                except Exception:
                    logger.exception("YooKassa webhook: failed to notify user %s", user.telegram_id)

    return {"status": "ok"}


# --------------- F4: Widget endpoints ---------------


_widget_subscribers: dict[str, list[asyncio.Queue]] = {}


@api.post("/widget/message")
async def widget_message(request: Request) -> dict:
    """F4: Входящее сообщение из веб-виджета.

    Создаёт виртуального пользователя с source_channel='widget',
    перенаправляет сообщение через PTB update queue.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    session_id = body.get("session_id", "")
    text = body.get("text", "").strip()

    if not session_id or not session_id.startswith("widget_"):
        raise HTTPException(status_code=400, detail="Invalid session_id")
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")
    if _ptb_app is None:
        raise HTTPException(status_code=503, detail="Bot not ready")

    from src.db.models import User, WidgetSession
    from src.db.session import async_session_factory
    from sqlalchemy import select

    factory = async_session_factory()
    async with factory() as session:
        ws = (await session.execute(
            select(WidgetSession).where(WidgetSession.session_id == session_id)
        )).scalar_one_or_none()

        if ws is None:
            # Создаём виртуального user + session
            virtual_tg_id = abs(hash(session_id)) % (10 ** 12) + 10 ** 12
            user_row = User(
                telegram_id=virtual_tg_id,
                widget_session_id=session_id,
                source_channel="widget",
            )
            session.add(user_row)
            await session.flush()
            ws = WidgetSession(
                session_id=session_id,
                user_id=user_row.id,
                page_referrer=body.get("referrer"),
                utm_source=body.get("utm_source"),
                utm_campaign=body.get("utm_campaign"),
            )
            session.add(ws)
            await session.commit()
            tg_id = virtual_tg_id
        else:
            tg_id = (await session.execute(
                select(User.telegram_id).where(User.id == ws.user_id)
            )).scalar_one()
            await session.commit()

    # Строим синтетический Update и кладём в очередь PTB
    synthetic = {
        "update_id": abs(hash(f"{session_id}:{text}")) % (2 ** 31),
        "message": {
            "message_id": abs(hash(f"{session_id}:{text}:msg")) % (2 ** 31),
            "from": {
                "id": tg_id,
                "is_bot": False,
                "first_name": "WebWidget",
                "language_code": "ru",
            },
            "chat": {"id": tg_id, "type": "private"},
            "date": int(asyncio.get_event_loop().time()),
            "text": text,
        },
    }
    update_obj = Update.de_json(synthetic, _ptb_app.bot)
    await _ptb_app.update_queue.put(update_obj)
    return {"status": "queued", "session_id": session_id}


@api.get("/widget/stream/{session_id}")
async def widget_stream(session_id: str) -> StreamingResponse:
    """F4: SSE endpoint — реал-тайм ответы бота в виджет."""
    if not session_id.startswith("widget_"):
        raise HTTPException(status_code=400, detail="Invalid session_id")

    queue: asyncio.Queue = asyncio.Queue()
    _widget_subscribers.setdefault(session_id, []).append(queue)

    async def event_generator():
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            subs = _widget_subscribers.get(session_id, [])
            if queue in subs:
                subs.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def push_widget_message(session_id: str, message: dict) -> None:
    """Публикует сообщение бота в SSE-стримы виджета для данной сессии."""
    for q in list(_widget_subscribers.get(session_id, [])):
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            pass


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "src.main:api",
        host="0.0.0.0",
        port=port,
        log_level=settings.log_level.lower(),
        reload=settings.environment == "development",
    )


if __name__ == "__main__":
    main()
