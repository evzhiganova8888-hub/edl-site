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
            InlineKeyboardButton("🚀 Я уже оплатил — продолжить Чекап", callback_data="menu:checkup"),
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
        [
            InlineKeyboardButton("🔐 Войти как админ", callback_data="admin_login:hint"),
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
    """После MANUAL_PAYMENT_SUBMITTED — ожидание активации + Иван + меню."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔔 Уведомить, когда Иван активирует доступ",
                    callback_data="audit:notify_waiting",
                )
            ],
            _ivan_row(),
            [InlineKeyboardButton("← В главное меню", callback_data="menu:main")],
            feedback_row("payment"),
        ]
    )


def scope_guard_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после off-topic canned-ответа."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎯 Пройти Quiz", callback_data="menu:quiz")],
            [InlineKeyboardButton("📋 Чекап от 9 000 ₽", callback_data="menu:audit")],
            _ivan_row(),
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


def resume_checkup_keyboard() -> InlineKeyboardMarkup:
    """F7: Клавиатура для предложения продолжить паузу чекапа."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Продолжить Чекап", url="https://t.me/edl_os_bot?start=checkup")],
    ])


def quiz_site_cta_keyboard(quiz_session_id: str) -> InlineKeyboardMarkup:
    """Кнопка после deep-link audit_from_score_<UUID> — пришёл с сайта."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Бизнес-чекап · 9 000 ₽", callback_data="audit:start_purchase:base")],
        [InlineKeyboardButton("🎬 Чекап Plus · 14 000 ₽", callback_data="audit:start_purchase:plus")],
        [InlineKeyboardButton("← В меню", callback_data="menu:main")],
        feedback_row("quiz"),
    ])


# ── Чекап v2 ──────────────────────────────────────────────────────────────────

def checkup_mc_keyboard(q_idx: int, options: tuple[tuple[str, int], ...]) -> InlineKeyboardMarkup:
    """5 вариантов ответа на MC вопрос Чекапа v2.

    callback_data: `checkup:mc:<q_idx>:<score>` (score = 0/3/5/8/10).
    """
    rows = [
        [InlineKeyboardButton(label, callback_data=f"checkup:mc:{q_idx}:{score}")]
        for label, score in options
    ]
    rows.append([InlineKeyboardButton("⏸ Перерыв", callback_data="checkup:pause")])
    return InlineKeyboardMarkup(rows)


def checkup_numeric_keyboard(q_idx: int, allow_skip: bool = True) -> InlineKeyboardMarkup:
    """Под numeric вопросом — кнопки «Не знаю» (если разрешено) и «Перерыв»."""
    rows: list[list[InlineKeyboardButton]] = []
    if allow_skip:
        rows.append([
            InlineKeyboardButton("🤷 Не знаю — посчитаю позже", callback_data=f"checkup:num_skip:{q_idx}")
        ])
    rows.append([InlineKeyboardButton("⏸ Перерыв", callback_data="checkup:pause")])
    return InlineKeyboardMarkup(rows)


def checkup_section_break_keyboard(layer_code: str) -> InlineKeyboardMarkup:
    """После Q5/Q10/Q15 — продолжить или сделать перерыв."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Продолжить", callback_data=f"checkup:continue:{layer_code}")],
        [InlineKeyboardButton("⏸ Перерыв (вернусь позже)", callback_data="checkup:pause")],
    ])


def checkup_short_text_keyboard(q_idx: int) -> InlineKeyboardMarkup:
    """Под short-text вопросом — пример и перерыв."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Пример хорошего ответа", callback_data=f"checkup:example:{q_idx}")],
        [InlineKeyboardButton("⏸ Перерыв", callback_data="checkup:pause")],
    ])


def checkup_quality_followup_keyboard(q_idx: int) -> InlineKeyboardMarkup:
    """После неудачной проверки качества — «Дополнить» / «Оставить так»."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Дополнить ответ", callback_data=f"checkup:improve:{q_idx}")],
        [InlineKeyboardButton("👌 Оставить как есть", callback_data=f"checkup:keep:{q_idx}")],
    ])


def checkup_resume_or_restart_keyboard(app_id: str, current_idx: int) -> InlineKeyboardMarkup:
    """Pause/resume: продолжить с N или начать заново (если был legacy)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"▶️ Продолжить с вопроса {current_idx + 1}/20",
            callback_data=f"checkup:resume:{app_id}",
        )],
        [InlineKeyboardButton("🔄 Начать заново", callback_data=f"checkup:restart:{app_id}")],
        [InlineKeyboardButton("← В меню", callback_data="menu:main")],
    ])


def checkup_v2_intro_keyboard(app_id: str, has_mini: bool) -> InlineKeyboardMarkup:
    """Intro перед Q1: «Поехали» / «Как это устроено»."""
    rows = [[InlineKeyboardButton("✅ Поехали", callback_data=f"checkup:start_v2:{app_id}")]]
    rows.append([InlineKeyboardButton(
        "📖 Сначала расскажи как устроено",
        callback_data=f"checkup:explain:{app_id}",
    )])
    return InlineKeyboardMarkup(rows)


def checkup_p1_segment_keyboard(app_id: str) -> InlineKeyboardMarkup:
    """Pre-P1 в Чекапе если не было Mini — выбор сегмента (7 опций)."""
    segs = [
        ("edu",   "Онлайн-школа / EdTech"),
        ("mp",    "Маркетплейс / e-commerce"),
        ("it",    "IT / digital-агентство"),
        ("prod",  "Производство / опт"),
        ("serv",  "Услуги"),
        ("saas",  "B2B SaaS"),
        ("other", "Другое"),
    ]
    rows = [[InlineKeyboardButton(label, callback_data=f"checkup:p1:{code}")] for code, label in segs]
    return InlineKeyboardMarkup(rows)


def checkup_p2_stage_keyboard(app_id: str) -> InlineKeyboardMarkup:
    """Pre-P2 — команда + выручка (6 опций)."""
    opts = [
        ("start",              "1–10 чел · до 15 М ₽"),
        ("team",               "10–25 чел · 15–60 М ₽"),
        ("structure",          "25–50 чел · 60–200 М ₽"),
        ("maturity",           "50+ чел · 200 М+ ₽"),
        ("outlier_small_team", "Команда меньше, чем выручка предполагает"),
        ("outlier_big_team",   "Команда больше, чем выручка предполагает"),
    ]
    rows = [[InlineKeyboardButton(label, callback_data=f"checkup:p2:{code}")] for code, label in opts]
    return InlineKeyboardMarkup(rows)


def checkup_final_cta_keyboard(
    *,
    show_plus_upgrade: bool = False,
    diagnostic_price_rub: int = 45_000,
) -> InlineKeyboardMarkup:
    """Финальный экран после Q20: 3 CTA (ТЗ §11.4)."""
    rows = [
        [InlineKeyboardButton(
            f"📊 Хочу Диагностику · {diagnostic_price_rub:,} ₽".replace(",", " "),
            callback_data="menu:diagnostic",
        )],
    ]
    if show_plus_upgrade:
        rows.append([InlineKeyboardButton(
            "🎬 Доплатить до Plus · +5 000 ₽",
            callback_data="checkup:upgrade_to_plus",
        )])
    rows.append([InlineKeyboardButton("💬 Вопрос Ивану", url=f"https://t.me/{settings.sales_username}")])
    rows.append([InlineKeyboardButton("← В меню", callback_data="menu:main")])
    rows.append(feedback_row("checkup"))
    return InlineKeyboardMarkup(rows)


def checkup_plus_upgrade_keyboard() -> InlineKeyboardMarkup:
    """Upsell Base → Plus: «Доплатить» / «Не сейчас»."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ Доплатить 5 000 ₽ и получить Plus",
            callback_data="checkup:confirm_upgrade",
        )],
        [InlineKeyboardButton("Сейчас не нужно", callback_data="checkup:decline_upgrade")],
    ])
