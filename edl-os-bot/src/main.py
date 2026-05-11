"""Entry point — FastAPI + python-telegram-bot.

Поддерживает 2 режима:
- polling (по умолчанию, для локальной разработки)
- webhook (если задан WEBHOOK_BASE_URL — для продакшена)

HTTP endpoints:
- GET  /health — liveness
- POST /webhook — Telegram updates
- POST /payments/robokassa/result  — ResultURL (server-to-server callback)
- GET  /payments/robokassa/success — SuccessURL (browser redirect)
- GET  /payments/robokassa/fail    — FailURL (browser redirect)

Запуск: `python -m src.main`.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID

import uvicorn
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import select
from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from src.bot import texts
from src.bot.handlers import register
from src.core.config import settings
from src.core.notifications import build_payment_success_brief, send_to_admin_chat
from src.core.payments import RobokassaClient
from src.db.models import Application as ApplicationModel
from src.db.models import Payment, User
from src.db.session import async_session_factory

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


api = FastAPI(title="EDL OS Bot", version="0.2.0", lifespan=lifespan)


@api.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "use_webhook": settings.use_webhook,
        "robokassa_configured": RobokassaClient().configured,
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


# --------------------- Robokassa endpoints -----------------------


@api.post("/payments/robokassa/result")
async def robokassa_result(request: Request) -> PlainTextResponse:
    """ResultURL callback. Robokassa отправляет form-data, ждёт ответ `OK<InvId>`."""
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    logger.info("Robokassa result callback: inv_id=%s", params.get("InvId"))

    client = RobokassaClient()
    callback = client.verify_result_callback(params)
    if not callback:
        logger.warning("Robokassa signature invalid: %s", params)
        raise HTTPException(status_code=400, detail="bad signature")

    await _process_successful_payment(callback.inv_id, callback.amount_rub, params)
    return PlainTextResponse(f"OK{callback.inv_id}")


async def _process_successful_payment(
    inv_id: int, amount_rub: float, raw_params: dict[str, str]
) -> None:
    factory = async_session_factory()
    async with factory() as session:
        stmt = select(ApplicationModel).where(ApplicationModel.inv_id == inv_id)
        app = (await session.execute(stmt)).scalar_one_or_none()
        if app is None:
            logger.warning("ResultURL: application not found for inv_id=%s", inv_id)
            return
        user = await session.get(User, app.user_id)
        if user is None:
            logger.warning("ResultURL: user not found for application %s", app.id)
            return

        # Update payment
        pay_stmt = (
            select(Payment)
            .where(Payment.application_id == app.id)
            .where(Payment.status == "pending")
        )
        payment = (await session.execute(pay_stmt)).scalars().first()
        if payment is None:
            logger.warning("ResultURL: no pending payment for application %s", app.id)
        else:
            payment.status = "succeeded"
            payment.paid_at = datetime.now(timezone.utc)
            payment.provider_payment_id = raw_params.get("PaymentMethod", "")
            payment.fiscal_receipt_url = raw_params.get("ReceiptUrl")

        # Update application
        now = datetime.now(timezone.utc)
        app.status = "paid"
        app.payment_succeeded_at = now
        # 14-дневное окно отсчитывается с момента доставки материалов; здесь
        # консервативно стартуем с оплаты, скорректируется когда статус
        # перейдёт в delivered.
        app.refund_eligible_until = now + timedelta(days=14)

        # Лог
        from src.db.models import Event

        session.add(
            Event(
                user_id=user.id,
                event="payment_succeeded",
                payload={
                    "application_id": str(app.id),
                    "inv_id": inv_id,
                    "amount_rub": amount_rub,
                },
            )
        )
        await session.commit()

        brief = build_payment_success_brief(
            user=user,
            application=app,
            amount_rub=amount_rub,
            receipt_url=raw_params.get("ReceiptUrl"),
        )
        target_user_id = user.telegram_id

    # Сообщения уже после commit
    if _ptb_app is not None:
        try:
            await _ptb_app.bot.send_message(chat_id=target_user_id, text=texts.PAYMENT_SUCCEEDED)
        except Exception:
            logger.exception("Failed to notify user about successful payment")
        try:
            await send_to_admin_chat(_ptb_app.bot, brief)
        except Exception:
            logger.exception("Failed to send admin brief")


@api.get("/payments/robokassa/success", response_class=HTMLResponse)
async def robokassa_success() -> str:
    """SuccessURL — браузерный редирект пользователя после оплаты."""
    return (
        "<!doctype html><html lang=ru><meta charset=utf-8>"
        "<title>Оплата прошла</title>"
        "<body style='font-family:Inter,sans-serif;max-width:480px;margin:80px auto;padding:0 16px'>"
        "<h1>Оплата получена</h1>"
        "<p>Спасибо. Подтверждение и чек уже отправили в Telegram-бот "
        "<a href='https://t.me/edl_os_bot'>@edl_os_bot</a>.</p>"
        "<p>Иван свяжется в течение часа в рабочее окно "
        "(10:00–19:00 МСК Пн–Пт), чтобы согласовать звонок.</p>"
        "</body></html>"
    )


@api.get("/payments/robokassa/fail", response_class=HTMLResponse)
async def robokassa_fail() -> str:
    return (
        "<!doctype html><html lang=ru><meta charset=utf-8>"
        "<title>Оплата не прошла</title>"
        "<body style='font-family:Inter,sans-serif;max-width:480px;margin:80px auto;padding:0 16px'>"
        "<h1>Оплата не прошла</h1>"
        "<p>Можно попробовать ещё раз в боте: "
        "<a href='https://t.me/edl_os_bot'>@edl_os_bot</a> → /audit.</p>"
        "<p>Если что-то не получается — напишите Ивану: "
        "<a href='https://t.me/lvanKhudyakov'>@lvanKhudyakov</a>.</p>"
        "</body></html>"
    )


def main() -> None:
    uvicorn.run(
        "src.main:api",
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower(),
        reload=settings.environment == "development",
    )


if __name__ == "__main__":
    main()
