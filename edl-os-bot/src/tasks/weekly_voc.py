"""Voice-of-Customer еженедельная выгрузка (§E.2 ТЗ v3.1).

Запускается раз в неделю в понедельник 09:30 МСК через Celery beat.
Собирает агрегаты за прошедшие 7 дней в JSON-снимок и публикует:
1) пишет файл `weekly_voc/YYYY-MM-DD.json` (для аналитики/Grafana),
2) шлёт сводку в Sales-чат — Иван + Катя видят перед ритуалом в 10:00.

Сводка содержит:
- неразобранные bug_errors с превью текста бота,
- кол-во заявок/оплат/возвратов за неделю,
- rate_limit_hit и pd_in_inbound_text event counters,
- топ-5 самых длинных диалогов (по выходящим сообщениям бота).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.models import Application, BotError, Event, MessageLog, Payment, Refund
from src.db.session import async_session_factory
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_OUT_DIR = Path("weekly_voc")


@celery_app.task(name="src.tasks.weekly_voc.run_weekly")
def run_weekly() -> dict:
    """Синхронная обёртка для Celery."""
    return asyncio.run(_run_async())


async def _collect(session: AsyncSession, since: datetime) -> dict:
    # Неразобранные bug-report'ы
    bug_rows = (
        await session.execute(
            select(BotError, MessageLog.text)
            .join(MessageLog, BotError.message_log_id == MessageLog.id, isouter=True)
            .where(BotError.reviewed_at.is_(None))
            .order_by(BotError.reported_at.desc())
            .limit(20)
        )
    ).all()

    new_apps = await session.scalar(
        select(func.count(Application.id)).where(Application.created_at >= since)
    )
    paid_apps = await session.scalar(
        select(func.count(Application.id)).where(Application.payment_succeeded_at >= since)
    )
    refunds_count = await session.scalar(
        select(func.count(Refund.id)).where(Refund.requested_at >= since)
    )
    revenue_kop = (
        await session.scalar(
            select(func.sum(Payment.amount_kopecks))
            .where(Payment.status == "succeeded")
            .where(Payment.paid_at >= since)
        )
    ) or 0
    refund_kop = (
        await session.scalar(
            select(func.sum(Payment.amount_kopecks))
            .where(Payment.status == "refunded")
            .where(Payment.refunded_at >= since)
        )
    ) or 0

    # Event counters
    event_rows = (
        await session.execute(
            select(Event.event, func.count(Event.id))
            .where(Event.occurred_at >= since)
            .group_by(Event.event)
            .order_by(desc(func.count(Event.id)))
            .limit(15)
        )
    ).all()

    # Топ-5 пользователей по объёму диалога
    top_dialog = (
        await session.execute(
            select(MessageLog.user_id, func.count(MessageLog.id))
            .where(MessageLog.occurred_at >= since)
            .where(MessageLog.direction == "outbound")
            .group_by(MessageLog.user_id)
            .order_by(desc(func.count(MessageLog.id)))
            .limit(5)
        )
    ).all()

    return {
        "since": since.isoformat(),
        "until": datetime.now(timezone.utc).isoformat(),
        "applications_new": new_apps or 0,
        "applications_paid": paid_apps or 0,
        "refunds_requested": refunds_count or 0,
        "revenue_rub": (revenue_kop or 0) / 100,
        "refunded_rub": (refund_kop or 0) / 100,
        "event_counts": [
            {"event": ev, "count": cnt} for ev, cnt in event_rows
        ],
        "top_dialog_users": [
            {"user_id": uid, "outbound_msgs": cnt} for uid, cnt in top_dialog
        ],
        "unresolved_bug_errors": [
            {
                "id": err.id,
                "user_id": err.user_id,
                "reported_at": err.reported_at.isoformat() if err.reported_at else None,
                "bot_message_preview": (text or "")[:300],
                "user_comment": err.user_comment,
            }
            for err, text in bug_rows
        ],
    }


def _format_telegram_summary(report: dict) -> str:
    lines = [
        "📊 *Weekly VoC* · EDL OS Bot",
        f"_{report['since'][:10]} → {report['until'][:10]}_",
        "",
        f"• Заявок: {report['applications_new']}",
        f"• Оплачено: {report['applications_paid']}",
        f"• Возвратов: {report['refunds_requested']}",
        f"• Выручка: {report['revenue_rub']:,.0f} ₽",
    ]
    if report["refunded_rub"]:
        lines.append(f"• Возвращено: {report['refunded_rub']:,.0f} ₽")
    bugs = report["unresolved_bug_errors"]
    lines.append(f"• ⚠️ Bug-reports неразобранных: {len(bugs)}")
    if bugs:
        lines.append("\n*Топ нерешённых bug-reports:*")
        for b in bugs[:5]:
            preview = (b["bot_message_preview"] or "—")[:120].replace("\n", " ")
            lines.append(f"  · `#{b['id']}` u/{b['user_id']}: {preview}…")
    lines.append("\nПолный отчёт — `weekly_voc/{date}.json` в репо.")
    return "\n".join(lines)


async def _run_async() -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    factory = async_session_factory()
    async with factory() as session:
        report = await _collect(session, since)

    _OUT_DIR.mkdir(exist_ok=True)
    fname = _OUT_DIR / f"{datetime.now(timezone.utc).date().isoformat()}.json"
    fname.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Weekly VoC report saved: %s", fname)

    # Шлём в Sales-чат
    if settings.admin_chat_id and settings.bot_token:
        try:
            import httpx

            summary = _format_telegram_summary(report)
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.bot_token}/sendMessage",
                    json={
                        "chat_id": settings.admin_chat_id,
                        "text": summary,
                        "parse_mode": "Markdown",
                    },
                )
        except Exception:
            logger.exception("weekly_voc Telegram post failed")

    return report
