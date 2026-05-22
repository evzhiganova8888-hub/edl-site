"""Дневная сводка метрик пилота Чекап Plus v2.0 (ТЗ §11.3).

Каждое утро в 9:00 МСК отправляется в admin-чат:
- Сколько Чекапов в работе / завершено / возвращено.
- Конверсия Чекап Plus → активация купона → подтверждение Иваном.
- Среднее время прохождения 16 ответов.
- Fallback rate (сколько PDF сгенерировано через ARCHETYPE_FALLBACKS).
- NPS из feedback table.

Подсветка отклонений от target из ТЗ §11.3.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select

from src.core.config import settings
from src.db.models import Application, Coupon, Event, Feedback, Refund
from src.db.session import async_session_factory
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Target из ТЗ §11.3 (пилот 5 клиентов)
TARGET_PLUS_REVENUE_RUB = 70_000
TARGET_COUPON_USE_RATE = 0.4  # 40%
TARGET_REFUND_RATE = 0.2      # ≤20%
TARGET_AVG_PROGRESS_MINUTES = 90
TARGET_COMPLETION_RATE = 0.8  # ≥80%
TARGET_PDF_GEN_MINUTES = 5
TARGET_VIDEO_GEN_HOURS = 36
TARGET_FALLBACK_RATE = 0.1    # ≤10%


@celery_app.task(name="src.tasks.pilot_metrics.run_daily_digest")
def run_daily_digest() -> dict:
    return asyncio.run(_compute_and_send())


async def _compute_and_send() -> dict:
    metrics = await compute_metrics()
    text = format_digest(metrics)
    await _send_to_admin(text)
    return metrics


async def compute_metrics(window_days: int = 7) -> dict:
    """Метрики за последние N дней."""
    factory = async_session_factory()
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    async with factory() as session:
        # Все Чекапы за окно
        all_apps_stmt = (
            select(Application)
            .where(Application.type == "audit")
            .where(Application.created_at >= cutoff)
        )
        all_apps = (await session.execute(all_apps_stmt)).scalars().all()

        paid = [a for a in all_apps if a.status in ("paid", "refund_requested")]
        plus = [a for a in paid if (a.payload or {}).get("plan") == "plus"]
        completed = [a for a in paid if a.checkup_completed_at is not None]
        in_progress = [
            a for a in paid
            if a.checkup_completed_at is None
            and (a.checkup_current_question_index or 0) > 0
        ]

        # Среднее время прохождения
        avg_progress_minutes = _avg_progress_minutes(completed)

        # Среднее время от Q16 до PDF
        avg_pdf_minutes = _avg_pdf_minutes(completed)

        # Refund counts
        refund_stmt = (
            select(func.count(Refund.id))
            .where(Refund.requested_at >= cutoff)
        )
        refund_count = (await session.execute(refund_stmt)).scalar() or 0

        # Coupon stats
        coupons_stmt = (
            select(Coupon.status, func.count(Coupon.id))
            .where(Coupon.issued_at >= cutoff)
            .group_by(Coupon.status)
        )
        coupon_by_status = dict((await session.execute(coupons_stmt)).all())
        coupons_total = sum(coupon_by_status.values())
        coupons_used = coupon_by_status.get("used", 0)

        # Fallback rate из events
        fallback_stmt = (
            select(func.count(Event.id))
            .where(Event.event == "pdf_fallback_used")
            .where(Event.occurred_at >= cutoff)
        )
        fallback_count = (await session.execute(fallback_stmt)).scalar() or 0
        pdf_gen_count = max(len(completed), 1)
        fallback_rate = fallback_count / pdf_gen_count

        # NPS из feedback (если категория = praise / severity содержит число)
        feedback_stmt = (
            select(Feedback.severity)
            .where(Feedback.reported_at >= cutoff)
            .where(Feedback.category.in_(["praise", "idea"]))
        )
        nps_scores = [
            int(s) for s in (await session.execute(feedback_stmt)).scalars().all()
            if s and s.isdigit()
        ]
        avg_nps = (sum(nps_scores) / len(nps_scores)) if nps_scores else None

    return {
        "window_days": window_days,
        "total_paid": len(paid),
        "plus_count": len(plus),
        "completed": len(completed),
        "in_progress": len(in_progress),
        "refund_count": refund_count,
        "refund_rate": refund_count / max(len(paid), 1),
        "coupons_total": coupons_total,
        "coupons_used": coupons_used,
        "coupon_use_rate": coupons_used / max(coupons_total, 1) if coupons_total else 0,
        "avg_progress_minutes": avg_progress_minutes,
        "avg_pdf_minutes": avg_pdf_minutes,
        "fallback_count": fallback_count,
        "fallback_rate": fallback_rate,
        "completion_rate": len(completed) / max(len(paid), 1) if paid else 0,
        "plus_revenue_rub": len(plus) * 14_000,
        "avg_nps": avg_nps,
        "nps_sample_size": len(nps_scores),
    }


def _avg_progress_minutes(completed: list[Application]) -> int | None:
    deltas = []
    for app in completed:
        if app.checkup_started_at and app.checkup_completed_at:
            delta = (app.checkup_completed_at - app.checkup_started_at).total_seconds() / 60
            if 5 <= delta <= 600:  # фильтр аномалий
                deltas.append(delta)
    if not deltas:
        return None
    return int(sum(deltas) / len(deltas))


def _avg_pdf_minutes(completed: list[Application]) -> int | None:
    """Время от завершения опроса до генерации PDF (delivered_at)."""
    deltas = []
    for app in completed:
        if app.checkup_completed_at and app.delivered_at:
            delta = (app.delivered_at - app.checkup_completed_at).total_seconds() / 60
            if 0 <= delta <= 60:
                deltas.append(delta)
    if not deltas:
        return None
    return int(sum(deltas) / len(deltas))


def format_digest(m: dict) -> str:
    """Markdown-сводка для отправки в админ-чат."""
    def mark(value: float | int | None, target: float | int, *, lower_is_better: bool = False) -> str:
        if value is None:
            return "—"
        if lower_is_better:
            return "✅" if value <= target else "⚠️"
        return "✅" if value >= target else "⚠️"

    nps = f"{m['avg_nps']:.1f}/10 (n={m['nps_sample_size']})" if m["avg_nps"] else "нет данных"

    lines = [
        f"📊 *Сводка пилота · окно {m['window_days']} дней*",
        "",
        f"*Чекапы*",
        f"• Оплачено: {m['total_paid']} (из них Plus: {m['plus_count']})",
        f"• Завершено: {m['completed']} {mark(m['completion_rate'], TARGET_COMPLETION_RATE)} target ≥{int(TARGET_COMPLETION_RATE*100)}%",
        f"• В работе: {m['in_progress']}",
        "",
        f"*Воронка Plus → Диагностика*",
        f"• Купонов выдано: {m['coupons_total']}",
        f"• Купонов использовано: {m['coupons_used']} {mark(m['coupon_use_rate'], TARGET_COUPON_USE_RATE)} target ≥{int(TARGET_COUPON_USE_RATE*100)}%",
        "",
        f"*Возвраты*",
        f"• Refund-заявок: {m['refund_count']} {mark(m['refund_rate'], TARGET_REFUND_RATE, lower_is_better=True)} target ≤{int(TARGET_REFUND_RATE*100)}%",
        "",
        f"*SLA*",
        f"• Среднее время чекапа: {m['avg_progress_minutes'] or '—'} мин {mark(m['avg_progress_minutes'] or 999, TARGET_AVG_PROGRESS_MINUTES, lower_is_better=True)} target ≤{TARGET_AVG_PROGRESS_MINUTES} мин",
        f"• От Q16 до PDF: {m['avg_pdf_minutes'] or '—'} мин {mark(m['avg_pdf_minutes'] or 999, TARGET_PDF_GEN_MINUTES, lower_is_better=True)} target ≤{TARGET_PDF_GEN_MINUTES} мин",
        f"• Fallback rate: {m['fallback_rate']*100:.1f}% {mark(m['fallback_rate'], TARGET_FALLBACK_RATE, lower_is_better=True)} target ≤{int(TARGET_FALLBACK_RATE*100)}%",
        "",
        f"*Выручка Plus*: {m['plus_revenue_rub']:,} ₽ (target ≥{TARGET_PLUS_REVENUE_RUB:,} ₽)".replace(",", " "),
        f"*NPS*: {nps}",
    ]
    return "\n".join(lines)


async def _send_to_admin(text: str) -> None:
    """Best-effort отправка в admin-чат."""
    try:
        from src.main import _ptb_app  # type: ignore[attr-defined]
        if _ptb_app is None or not settings.admin_chat_id:
            return
        await _ptb_app.bot.send_message(
            chat_id=settings.admin_chat_id,
            text=text,
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Failed to send pilot digest to admin chat")
