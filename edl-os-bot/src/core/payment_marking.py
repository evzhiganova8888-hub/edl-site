"""Единая логика «отметить заявку как оплаченную».

Используется двумя путями:
- Robokassa ResultURL callback (src/main.py:_process_successful_payment) —
  автоматический server-to-server callback после оплаты картой.
- POST /admin/applications/{id}/mark-paid (src/admin/routes.py) — ручная
  отметка Иваном после получения денег по реквизитам в manual-режиме.

Логика идемпотентна: повторный вызов на уже оплаченной заявке не дублирует
события и не сдвигает refund_eligible_until.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Application, Event, Payment, User

logger = logging.getLogger(__name__)

REFUND_WINDOW_DAYS = 14


async def mark_application_paid(
    session: AsyncSession,
    *,
    app: Application,
    user: User,
    amount_rub: float,
    payment_provider: str = "robokassa",
    provider_payment_id: str | None = None,
    receipt_url: str | None = None,
    paid_at: datetime | None = None,
    payment_reference: str | None = None,
    actor: str = "system",
) -> dict:
    """Отмечает Application как оплаченное. Идемпотентно.

    Возвращает dict с инфо для последующих сообщений (юзеру + бриф Ивану).

    Если заявка уже paid — выходит без побочных эффектов, возвращает
    `{"already_paid": True}`.
    """
    now = paid_at or datetime.now(timezone.utc)

    if app.status == "paid":
        logger.info(
            "mark_application_paid: app %s already paid, skipping", app.id
        )
        return {"already_paid": True, "application_id": str(app.id)}

    # Найдём существующий pending Payment (для Robokassa) или создадим
    # новый (для manual режима, где Payment может не существовать).
    pay_stmt = (
        select(Payment)
        .where(Payment.application_id == app.id)
        .order_by(Payment.created_at.desc())
    )
    payment = (await session.execute(pay_stmt)).scalars().first()

    if payment is None:
        # Manual режим — Payment ещё не создан, создаём
        payment = Payment(
            application_id=app.id,
            user_id=user.id,
            amount_kopecks=int(round(amount_rub * 100)),
            currency="RUB",
            provider=payment_provider,
            provider_invoice_id=str(app.inv_id),
            status="succeeded",
            paid_at=now,
            provider_payment_id=provider_payment_id,
            fiscal_receipt_url=receipt_url,
        )
        session.add(payment)
    else:
        # Robokassa режим — Payment был создан как pending, обновляем
        payment.status = "succeeded"
        payment.paid_at = now
        if provider_payment_id:
            payment.provider_payment_id = provider_payment_id
        if receipt_url:
            payment.fiscal_receipt_url = receipt_url

    app.status = "paid"
    app.payment_succeeded_at = now
    app.refund_eligible_until = now + timedelta(days=REFUND_WINDOW_DAYS)

    session.add(
        Event(
            user_id=user.id,
            event="payment_succeeded",
            payload={
                "application_id": str(app.id),
                "inv_id": app.inv_id,
                "amount_rub": amount_rub,
                "provider": payment_provider,
                "payment_reference": payment_reference,
                "actor": actor,
            },
        )
    )
    return {
        "already_paid": False,
        "application_id": str(app.id),
        "amount_rub": amount_rub,
        "receipt_url": receipt_url,
        "refund_eligible_until": app.refund_eligible_until.isoformat(),
    }


async def find_application_by_id(
    session: AsyncSession, application_id: str
) -> Optional[Application]:
    """Удобный хелпер."""
    from uuid import UUID

    try:
        uid = UUID(application_id)
    except ValueError:
        return None
    stmt = select(Application).where(Application.id == uid)
    return (await session.execute(stmt)).scalar_one_or_none()
