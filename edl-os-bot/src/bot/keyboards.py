"""Inline + reply клавиатуры (segment-aware, по §7 ТЗ v3)."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.core.config import settings
from src.core.segment import SEGMENT_LABELS


def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🎯 Узнать, подходит ли мне", callback_data="menu:quiz"),
        ],
        [
            InlineKeyboardButton("📅 Бесплатное демо · 30 мин", callback_data="menu:demo"),
        ],
        [
            InlineKeyboardButton("📋 Бизнес-чекап · 9 000 ₽", callback_data="menu:audit"),
            InlineKeyboardButton("📄 Пример отчёта", callback_data="menu:audit_sample"),
        ],
        [
            InlineKeyboardButton("🏗 Лист ожидания Спринта", callback_data="menu:sprint_waitlist"),
        ],
        [
            InlineKeyboardButton(
                "💬 Написать Ивану", url=f"https://t.me/{settings.sales_username}"
            ),
        ],
        [
            InlineKeyboardButton("❓ FAQ", callback_data="menu:faq"),
            InlineKeyboardButton("🔒 Мои данные", callback_data="menu:privacy"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Даю согласие", callback_data="consent:accept")],
            [InlineKeyboardButton("❌ Не сейчас", callback_data="consent:decline")],
            [InlineKeyboardButton("📜 Политика", url=settings.privacy_policy_url)],
        ]
    )


def segments_keyboard() -> InlineKeyboardMarkup:
    """Сетка 2×4 + other."""
    keys = [
        "manufacturing",
        "wholesale",
        "services_legal",
        "services_it",
        "services_marketing_agency",
        "b2b_saas",
        "marketplace_accounting",
        "marketplace_logistics",
    ]
    rows = []
    for i in range(0, len(keys), 2):
        row = [
            InlineKeyboardButton(SEGMENT_LABELS[k], callback_data=f"segment:{k}")
            for k in keys[i : i + 2]
        ]
        rows.append(row)
    rows.append([InlineKeyboardButton("Другое", callback_data="segment:other")])
    return InlineKeyboardMarkup(rows)


def audit_pay_keyboard(invoice_url: str | None = None) -> InlineKeyboardMarkup:
    """Кнопка оплаты Чекапа. На MVP Этапа 1 без реальной ссылки — заглушка."""
    buttons = []
    if invoice_url:
        buttons.append([InlineKeyboardButton("💳 Оплатить 9 000 ₽", url=invoice_url)])
    buttons.append(
        [InlineKeyboardButton("📄 Сначала посмотреть пример", callback_data="menu:audit_sample")]
    )
    buttons.append(
        [InlineKeyboardButton(f"💬 Спросить Ивана", url=f"https://t.me/{settings.sales_username}")]
    )
    return InlineKeyboardMarkup(buttons)


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("← В главное меню", callback_data="menu:main")]]
    )
