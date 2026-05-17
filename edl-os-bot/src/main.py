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
        logger.info("Webhook set to %s", webhook_url)
    else:
        asyncio.create_task(_run_polling(_ptb_app))
        logger.info("Polling started")

    try:
        yield
    finally:
        if settings.use_webhook:
            try:
                await _ptb_app.bot.delete_webhook()
            except Exception:
                logger.exception("delete_webhook failed")
        await _ptb_app.stop()
        await _ptb_app.shutdown()


async def _run_polling(app: Application) -> None:
    try:
        await app.updater.start_polling(drop_pending_updates=True)
    except Exception:
        logger.exception("polling failed")


api = FastAPI(title="EDL OS Bot", version="0.3.2", lifespan=lifespan)
api.include_router(admin_router)


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
    if (
        settings.webhook_secret_token
        and x_telegram_bot_api_secret_token != settings.webhook_secret_token
    ):
        raise HTTPException(status_code=401, detail="Invalid secret token")
    if _ptb_app is None:
        raise HTTPException(status_code=503, detail="Bot is not ready")
    data = await request.json()
    update = Update.de_json(data, _ptb_app.bot)
    await _ptb_app.process_update(update)
    return {"ok": True}


def main() -> None:
    # Railway инжектит PORT env var; локально — 8000.
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "src.main:api",
        host="0.0.0.0",
        port=port,
        log_level=settings.log_level.lower(),
        reload=settings.environment == "development",
    )


if __name__ == "__main__":
    main()
