"""Entry point — FastAPI + python-telegram-bot.

Поддерживает 2 режима:
- polling (по умолчанию, для локальной разработки)
- webhook (если задан WEBHOOK_BASE_URL — для продакшена)

HTTP endpoints:
- GET  /health — liveness
- POST /webhook — Telegram updates

Запуск: `python -m src.main`.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from src.admin.routes import router as admin_router
from src.bot.handlers import register
from src.core.config import settings

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


api = FastAPI(title="EDL OS Bot", version="0.3.2", lifespan=lifespan)
api.include_router(admin_router)


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
