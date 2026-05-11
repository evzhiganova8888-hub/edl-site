"""Admin REST endpoints — заявки, платежи, метрики, toggles."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from src.admin.auth import require_admin
from src.core.flags import FLAG_VITACONSULT_PUBLIC, get_flag, set_flag
from src.db.models import Application, Event, Payment, User
from src.db.session import async_session_factory

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def stats(admin_id: int = Depends(require_admin)) -> dict:
    """Funnel-метрики: события + платежи за 30 дней."""
    factory = async_session_factory()
    since = datetime.now(timezone.utc) - timedelta(days=30)
    async with factory() as session:
        evt_stmt = (
            select(Event.event, func.count(Event.id))
            .where(Event.occurred_at >= since)
            .group_by(Event.event)
            .order_by(func.count(Event.id).desc())
        )
        events = {row[0]: row[1] for row in (await session.execute(evt_stmt)).all()}

        pay_stmt = (
            select(Payment.status, func.count(Payment.id), func.sum(Payment.amount_kopecks))
            .where(Payment.created_at >= since)
            .group_by(Payment.status)
        )
        payments = {
            row[0]: {"count": row[1], "amount_rub": (row[2] or 0) / 100}
            for row in (await session.execute(pay_stmt)).all()
        }

        seg_stmt = (
            select(User.segment, func.count(User.id))
            .where(User.created_at >= since)
            .group_by(User.segment)
        )
        segments = {row[0] or "unknown": row[1] for row in (await session.execute(seg_stmt)).all()}

        return {
            "since": since.isoformat(),
            "events": events,
            "payments": payments,
            "new_users_by_segment": segments,
        }


@router.get("/applications")
async def list_applications(
    admin_id: int = Depends(require_admin),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
) -> list[dict]:
    factory = async_session_factory()
    async with factory() as session:
        stmt = select(Application).order_by(Application.created_at.desc()).limit(limit)
        if status_filter:
            stmt = stmt.where(Application.status == status_filter)
        rows = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": str(a.id),
                "inv_id": a.inv_id,
                "user_id": a.user_id,
                "type": a.type,
                "status": a.status,
                "source": a.source,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "payment_succeeded_at": a.payment_succeeded_at.isoformat()
                if a.payment_succeeded_at else None,
                "refund_eligible_until": a.refund_eligible_until.isoformat()
                if a.refund_eligible_until else None,
                "payload": a.payload,
            }
            for a in rows
        ]


@router.get("/payments")
async def list_payments(
    admin_id: int = Depends(require_admin),
    limit: int = Query(default=50, le=200),
) -> list[dict]:
    factory = async_session_factory()
    async with factory() as session:
        stmt = select(Payment).order_by(Payment.created_at.desc()).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        return [
            {
                "id": str(p.id),
                "application_id": str(p.application_id),
                "user_id": p.user_id,
                "amount_rub": p.amount_kopecks / 100,
                "currency": p.currency,
                "provider": p.provider,
                "status": p.status,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                "fiscal_receipt_url": p.fiscal_receipt_url,
            }
            for p in rows
        ]


@router.get("/users/{telegram_id}")
async def get_user(telegram_id: int, admin_id: int = Depends(require_admin)) -> dict:
    factory = async_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return {"detail": "not found"}
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "telegram_username": user.telegram_username,
            "segment": user.segment,
            "sub_profile": user.sub_profile,
            "stage": user.stage,
            "email": user.email,
            "phone": user.phone,
            "company_name": user.company_name,
            "quiz_score": user.quiz_score,
            "consent_pd_given_at": user.consent_pd_given_at.isoformat()
            if user.consent_pd_given_at else None,
        }


@router.get("/flags/{key}")
async def get_flag_route(key: str, admin_id: int = Depends(require_admin)) -> dict:
    factory = async_session_factory()
    async with factory() as session:
        value = await get_flag(session, key)
    return {"key": key, "enabled": value}


@router.post("/flags/{key}")
async def set_flag_route(
    key: str,
    enabled: bool = Query(...),
    admin_id: int = Depends(require_admin),
) -> dict:
    factory = async_session_factory()
    async with factory() as session:
        await set_flag(session, key, enabled=enabled, actor=str(admin_id))
        await session.commit()
        new_value = await get_flag(session, key)
    return {"key": key, "enabled": new_value, "updated_by": admin_id}
