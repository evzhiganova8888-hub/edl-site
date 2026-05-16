"""Бриф-уведомления Ивану в Sales-чат (§12.3 ТЗ v3)."""
from __future__ import annotations

import logging
from datetime import timedelta

from telegram import Bot

from src.core.config import settings
from src.core.handoff import get_rule
from src.core.segment import SEGMENT_LABELS
from src.core.working_hours import humanize_window, is_working_now, next_business_window
from src.db.models import Application, User

logger = logging.getLogger(__name__)


def build_lead_brief(
    *,
    user: User,
    application: Application | None,
    extra_context: str = "",
) -> str:
    """Возвращает текст брифа по шаблону §12.3 ТЗ."""
    segment = user.segment or "other"
    rule = get_rule(segment)

    if is_working_now():
        sla = f"{rule.sla_label} (в рабочее окно)"
    else:
        deadline = next_business_window() + timedelta(hours=rule.sla_hours)
        sla = f"{rule.sla_label} · до {humanize_window(deadline)}"

    contact_lines = []
    if user.telegram_username:
        contact_lines.append(f"TG: @{user.telegram_username}")
    if user.email:
        contact_lines.append(f"Email: {user.email}")
    if user.phone:
        contact_lines.append(f"Телефон: {user.phone}")
    if not contact_lines:
        contact_lines.append(f"TG user_id: {user.telegram_id}")
    contact = "\n".join(contact_lines)

    company = []
    if user.company_name:
        company.append(user.company_name)
    if user.company_size:
        company.append(f"{user.company_size} чел")
    if user.company_revenue_range:
        company.append(user.company_revenue_range)
    company_line = ", ".join(company) if company else "—"

    app_type = application.type if application else "—"
    app_source = application.source if (application and application.source) else "—"

    lines = [
        "📥 НОВЫЙ ЛИД ИЗ БОТА @edl_os_bot",
        "",
        f"Сегмент: {SEGMENT_LABELS.get(segment, segment)} / {user.stage or 'cold'}",
    ]
    if user.sub_profile:
        lines.append(f"Под-профиль: {user.sub_profile}")
    lines.extend(
        [
            f"Тип заявки: {app_type}",
            f"Источник: {app_source}",
            f"Компания: {company_line}",
            "",
            "Контакт:",
            contact,
        ]
    )
    if extra_context:
        lines.extend(["", "Контекст:", extra_context])
    lines.extend(
        [
            "",
            f"Канал hand-off: {rule.channel}",
            f"SLA: {sla}",
        ]
    )
    if user.quiz_score is not None:
        lines.append(f"Quiz Score: {user.quiz_score}")
    return "\n".join(lines)


async def send_to_admin_chat(bot: Bot, text: str) -> bool:
    """Отправляет сообщение в ADMIN_CHAT_ID. Возвращает True/False."""
    if not settings.admin_chat_id:
        logger.warning("ADMIN_CHAT_ID not set — skipping admin notification")
        return False
    try:
        await bot.send_message(chat_id=settings.admin_chat_id, text=text)
        return True
    except Exception:
        logger.exception("Failed to send admin notification")
        return False


def build_payment_success_brief(
    *,
    user: User,
    application: Application,
    amount_rub: float,
    receipt_url: str | None,
) -> str:
    lines = [
        "💰 ОПЛАТА ПОЛУЧЕНА",
        "",
        f"Продукт: {application.type}",
        f"Сумма: {amount_rub:.0f} ₽",
        f"Сегмент: {SEGMENT_LABELS.get(user.segment or 'other', user.segment or '—')}",
        "",
        f"Email: {user.email or '—'}",
        f"TG: @{user.telegram_username or '—'} (id {user.telegram_id})",
    ]
    if receipt_url:
        lines.append(f"Чек: {receipt_url}")
    lines.extend(
        [
            "",
            f"Связаться в течение часа в рабочее окно (10:00–19:00 МСК Пн–Пт).",
        ]
    )
    return "\n".join(lines)


def build_manual_payment_brief(
    *,
    user: User,
    application: Application,
    plan: str,
    amount_rub: float,
    full_name: str | None,
    company: str | None,
) -> str:
    """Бриф Ивану для ручного оформления счёта в manual-payment режиме (Май 2026,
    до активации Robokassa)."""
    plan_label = "Plus" if plan == "plus" else "Базовый"
    plan_details = (
        "PDF-отчёт по 4 слоям + FigJam + 3 действия на неделю + 90-дневный план"
        if plan == "base"
        else "Всё из Базового + персональный видео-разбор от Кати"
    )
    lines = [
        "🧾 РУЧНОЙ ПЛАТЁЖ — оформить счёт",
        "",
        f"Тариф: {plan_label} · {amount_rub:.0f} ₽",
        f"Состав: {plan_details}",
        "",
        "Контактные данные клиента:",
        f"  ФИО: {full_name or '—'}",
        f"  Email: {user.email or '—'}",
        f"  Компания: {company or '—'}",
        f"  TG: @{user.telegram_username or '—'} (id {user.telegram_id})",
        f"  Сегмент: {SEGMENT_LABELS.get(user.segment or 'other', user.segment or '—')}",
        "",
        f"Application ID (для трекинга): {application.id}",
        f"Inv ID: {application.inv_id}",
        "",
        "Что сделать:",
        "1. Передать ФИО + email + компанию в бухгалтерию, попросить счёт.",
        "2. Прислать клиенту счёт на email.",
        "3. После прихода денег на расчётный счёт — пометить оплату:",
        f"   POST /admin/applications/{application.id}/mark-paid",
        "",
        "Чтобы активировать Чекап после прихода денег — отправь в бот:",
        f"   /mark_paid {application.id} {amount_rub:.0f} \"счёт-НОМЕР\"",
        "",
        "Связаться с клиентом в течение часа в рабочее окно (10:00–19:00 МСК Пн–Пт).",
    ]
    return "\n".join(lines)


def build_refund_request_brief(
    *,
    user: User,
    application: Application,
    reason: str,
) -> str:
    return (
        "↩️ ЗАПРОС ВОЗВРАТА\n\n"
        f"Продукт: {application.type}\n"
        f"Email: {user.email or '—'}\n"
        f"TG: @{user.telegram_username or '—'} (id {user.telegram_id})\n\n"
        f"Причина: {reason or '—'}\n\n"
        "В Robokassa подтвердить refund вручную. SLA — 5 рабочих дней."
    )
