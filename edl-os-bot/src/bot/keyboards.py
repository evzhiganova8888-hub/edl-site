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
            InlineKeyboardButton("📋 Чекап · от 9 000 ₽", callback_data="menu:audit"),
            InlineKeyboardButton("📄 Пример отчёта", callback_data="menu:audit_sample"),
        ],
        [
            InlineKeyboardButton("🏗 Лист ожидания Спринта", callback_data="menu:sprint_waitlist"),
        ],
        [
            InlineKeyboardButton(
                "💬 Написать Ивану напрямую", url=f"https://t.me/{settings.sales_username}"
            ),
        ],
        [
            InlineKeyboardButton("❓ FAQ", callback_data="menu:faq"),
            InlineKeyboardButton("🔒 Мои данные", callback_data="menu:privacy"),
        ],
        # Beta 12.05-19.05: ОС по любому шагу.
        feedback_row("welcome"),
    ]
    return InlineKeyboardMarkup(rows)


def _ivan_row() -> list[InlineKeyboardButton]:
    """«К Ивану напрямую» — escape hatch на каждом экране (D.2 v3.1)."""
    return [
        InlineKeyboardButton(
            "💬 Написать Ивану напрямую",
            url=f"https://t.me/{settings.sales_username}",
        )
    ]


def consent_keyboard() -> InlineKeyboardMarkup:
    # «К Ивану» убрана — на этом первом экране лишний шум, юзер ещё
    # не дошёл до сути. Доступна через /menu.
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


def audit_pay_keyboard(
    invoice_url: str | None = None, *, plan: str = "base"
) -> InlineKeyboardMarkup:
    """Кнопка оплаты Чекапа. URL появляется после согласия + оферты + email.

    plan: 'base' (9 000 ₽) | 'plus' (14 000 ₽ — с видео-разбором от Кати).
    """
    buttons: list[list[InlineKeyboardButton]] = []
    if invoice_url:
        label = "💳 Оплатить 14 000 ₽" if plan == "plus" else "💳 Оплатить 9 000 ₽"
        buttons.append([InlineKeyboardButton(label, url=invoice_url)])
    else:
        buttons.append(
            [
                InlineKeyboardButton(
                    "🛒 Чекап Базовый · 9 000 ₽",
                    callback_data="audit:start_purchase:base",
                )
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    "🎥 Чекап Plus · 14 000 ₽ (с видео Кати)",
                    callback_data="audit:start_purchase:plus",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton("📄 Сначала пример отчёта", callback_data="menu:audit_sample")]
    )
    buttons.append(_ivan_row())
    buttons.append(feedback_row("audit"))
    return InlineKeyboardMarkup(buttons)


def offer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📜 Открыть полный текст оферты", url=settings.offer_url)],
            [InlineKeyboardButton("✅ Я принимаю оферту", callback_data="offer:accept")],
            [InlineKeyboardButton("❌ Не сейчас", callback_data="offer:decline")],
            _ivan_row(),
            feedback_row("offer"),
        ]
    )


def refund_keyboard(application_id: str) -> InlineKeyboardMarkup:
    """1-click refund (§D.6 v3.1): запускаем возврат сразу, причина — потом и опционально."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "↩️ Получить возврат",
                    callback_data=f"refund:request:{application_id}",
                )
            ],
            [InlineKeyboardButton("← В меню", callback_data="menu:main")],
            _ivan_row(),
        ]
    )


def cancel_collection_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Отменить", callback_data="audit:cancel_collection")]]
    )


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("← В главное меню", callback_data="menu:main")]]
    )


def payment_submitted_keyboard() -> InlineKeyboardMarkup:
    """После MANUAL_PAYMENT_SUBMITTED — меню + ОС по шагу оплаты."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("← В главное меню", callback_data="menu:main")],
            _ivan_row(),
            feedback_row("payment"),
        ]
    )


def bug_report_keyboard(message_log_id: int) -> InlineKeyboardMarkup:
    """Кнопки под ответом AI (beta 12.05-19.05): полезно / неточно / Ивану.

    «🤔 Неточно» = bug-report (см. handle_callback в bug_report.py).
    «👍 Полезно» = praise feedback на step=ai_reply.
    «💬 К Ивану» = escape hatch (D.2 v3.1).
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👍 Полезно",
                    callback_data=f"feedback:praise_ai:{message_log_id}",
                ),
                InlineKeyboardButton(
                    "🤔 Неточно",
                    callback_data=f"bugreport:msg:{message_log_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "💬 К Ивану", url=f"https://t.me/{settings.sales_username}"
                ),
            ],
        ]
    )


def bug_report_skip_keyboard() -> InlineKeyboardMarkup:
    """После «Ответ неверный» — необязательный комментарий."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Пропустить", callback_data="bugreport:skip")]]
    )


def feedback_button(step: str) -> InlineKeyboardButton:
    """Кнопка «💬 ОС по этому шагу» для встраивания в любую клавиатуру (beta)."""
    return InlineKeyboardButton(
        "💬 ОС по этому шагу", callback_data=f"feedback:start:{step}"
    )


def feedback_row(step: str) -> list[InlineKeyboardButton]:
    return [feedback_button(step)]


def feedback_categories_keyboard(step: str) -> InlineKeyboardMarkup:
    """4 категории: баг / не хватает / идея / понравилось + пропустить."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👾 Баг", callback_data=f"feedback:cat:{step}:bug"),
                InlineKeyboardButton(
                    "🤔 Не хватает", callback_data=f"feedback:cat:{step}:missing"
                ),
            ],
            [
                InlineKeyboardButton(
                    "💡 Идея", callback_data=f"feedback:cat:{step}:idea"
                ),
                InlineKeyboardButton(
                    "👍 Понравилось", callback_data=f"feedback:cat:{step}:praise"
                ),
            ],
            [InlineKeyboardButton("Отменить", callback_data="feedback:cancel")],
        ]
    )


def feedback_after_comment_keyboard(step: str) -> InlineKeyboardMarkup:
    """После выбора категории — пропустить комментарий или отменить целиком."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Пропустить комментарий", callback_data=f"feedback:skip:{step}"
                )
            ],
            [
                InlineKeyboardButton(
                    "Отменить ОС", callback_data="feedback:cancel"
                )
            ],
        ]
    )


def followup_subscribe_keyboard(step: str) -> InlineKeyboardMarkup:
    """Email-подписка на отчёт «что мы сделали по ОС» (beta-крючок)."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📬 Хочу отчёт на email",
                    callback_data=f"feedback:email:{step}",
                )
            ],
            [
                InlineKeyboardButton(
                    "Спасибо, не надо", callback_data=f"feedback:nomail:{step}"
                )
            ],
        ]
    )


def waitlist_keyboard(slot: str) -> InlineKeyboardMarkup:
    """Заглушка с CTA «попасть в waitlist» для нерабочих экранов beta.

    slot: 'video_review' | 'calendly' | 'audit_pdf' — пишется в payload.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔔 Хочу попробовать первым",
                    callback_data=f"waitlist:join:{slot}",
                )
            ],
            [
                InlineKeyboardButton(
                    "💬 Написать Ивану напрямую",
                    url=f"https://t.me/{settings.sales_username}",
                )
            ],
            feedback_row("other"),
        ]
    )
