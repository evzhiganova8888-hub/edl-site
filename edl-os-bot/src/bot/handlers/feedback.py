"""Структурированная обратная связь от пользователя (beta 12.05-19.05).

Двухуровневый FSM:
  1. callback `feedback:start:<step>` → показать 4 категории
  2. callback `feedback:cat:<step>:<category>` → попросить комментарий (FSM)
  3. text-input → записать комментарий + предложить email-подписку
  4. callback `feedback:email:<step>` → выставить wants_followup_report=True
  5. callback `feedback:skip:<step>` / `feedback:nomail:<step>` / `feedback:cancel`

Дополнительно:
  - `feedback:praise_ai:<message_log_id>` — отдельная ветка для «👍 Полезно»
    под ответом AI (быстрый praise без комментария).
  - `feedback:waitlist:<slot>` — фиксируем хочу-в-waitlist.

Админ:
  - /feedback — пагинация unresolved (как /bugs)
  - /feedback export — md-выгрузка
  - callback `feedback:review:resolve|patched|ignore|page:<id>` — пометить
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.admin.auth import is_admin
from src.bot import keyboards
from src.core.feedback import CATEGORIES, record_feedback
from src.db.models import Feedback, User
from src.db.repos import get_or_create_user, log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

# user_data ключи
_FB_STEP = "fb_pending_step"
_FB_CAT = "fb_pending_category"
_FB_ID = "fb_pending_id"

_PAGE_SIZE = 5


# ───────────────────────────── USER FLOW ─────────────────────────────


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Главный диспетчер для всех `feedback:*` callback-ов."""
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = (query.data or "").split(":")
    if len(data) < 2:
        return
    action = data[1]

    if action == "start" and len(data) >= 3:
        await _start_flow(update, context, step=data[2])
        return
    if action == "cancel":
        _clear(context)
        await query.message.reply_text("Окей, не записываю. /menu — главное меню.")
        return
    if action == "cat" and len(data) >= 4:
        await _select_category(update, context, step=data[2], category=data[3])
        return
    if action == "skip" and len(data) >= 3:
        await _finalize_without_comment(update, context, step=data[2])
        return
    if action == "email" and len(data) >= 3:
        await _subscribe_email(update, context, step=data[2], wants=True)
        return
    if action == "nomail" and len(data) >= 3:
        await _subscribe_email(update, context, step=data[2], wants=False)
        return
    if action == "praise_ai" and len(data) >= 3:
        await _quick_praise_ai(update, context, message_log_id=data[2])
        return
    if action == "review" and len(data) >= 3:
        await _review_callback(update, data[2:])
        return


async def _start_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, *, step: str) -> None:
    context.user_data[_FB_STEP] = step
    await update.callback_query.message.reply_text(
        "Что хотите отметить по этому шагу?\n\n"
        "👾 *Баг* — что-то не сработало или сломалось\n"
        "🤔 *Не хватает* — на экране не было нужного\n"
        "💡 *Идея* — что добавить или сделать иначе\n"
        "👍 *Понравилось* — что зашло (нам тоже важно знать)\n\n"
        "Это занимает 30 секунд. Спасибо, что помогаете.",
        reply_markup=keyboards.feedback_categories_keyboard(step),
        parse_mode="Markdown",
    )


async def _select_category(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, step: str, category: str
) -> None:
    if category not in CATEGORIES:
        category = "missing"
    context.user_data[_FB_STEP] = step
    context.user_data[_FB_CAT] = category

    # Подсказки специально конкретные — это улучшает actionability ОС:
    # вместо «всё плохо» получаем «жму X, ждал Y, увидел Z».
    prompts = {
        "bug": (
            "Что именно сломалось? Чтобы починить быстро, помогите так:\n"
            "1) что вы сделали (нажал X / написал Y);\n"
            "2) что ожидали увидеть;\n"
            "3) что увидели на самом деле.\n"
            "Одно сообщение, можно коротко."
        ),
        "missing": (
            "Чего не хватило на этом шаге?\n"
            "Что бы вы хотели увидеть здесь — цифру, кнопку, объяснение, "
            "пример? Опишите одной фразой."
        ),
        "idea": (
            "Расскажите идею.\n"
            "Если можно — два слова про контекст (для какой задачи / "
            "когда бы это пригодилось). Мы посмотрим, как встроить."
        ),
        "praise": (
            "Что именно понравилось?\n"
            "(Можно пропустить — мы и так рады. Но если назовёте «вот это "
            "зашло» — будем знать, чего не сломать.)"
        ),
    }
    text = prompts.get(category, "Расскажите подробнее (одно сообщение).")
    await update.callback_query.message.reply_text(
        text, reply_markup=keyboards.feedback_after_comment_keyboard(step)
    )


async def _finalize_without_comment(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, step: str
) -> None:
    category = context.user_data.get(_FB_CAT, "missing")
    already_subscribed = False
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(
            session, telegram_id=update.effective_user.id
        )
        fb_id = await record_feedback(
            session, user_id=user.id, step=step, category=category, comment=None
        )
        already_subscribed = bool(user.wants_followup_report)
        await session.commit()

    context.user_data[_FB_ID] = fb_id
    _clear_pending_text(context)
    if already_subscribed:
        await update.callback_query.message.reply_text(
            "Спасибо, записала. Вы уже подписаны на email-отчёт — пришлём 20 мая."
        )
    else:
        await update.callback_query.message.reply_text(
            "Спасибо, записала. " + _email_pitch(),
            reply_markup=keyboards.followup_subscribe_keyboard(step),
        )


async def handle_text_step(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Принять текстовый комментарий, если ждём его. Возвращает True если FSM сработал."""
    step = context.user_data.get(_FB_STEP)
    category = context.user_data.get(_FB_CAT)
    if not step or not category:
        return False

    text = (update.effective_message.text or "").strip()
    already_subscribed = False
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(
            session, telegram_id=update.effective_user.id
        )
        fb_id = await record_feedback(
            session,
            user_id=user.id,
            step=step,
            category=category,
            comment=text[:2000] if text else None,
        )
        already_subscribed = bool(user.wants_followup_report)
        await session.commit()

    context.user_data[_FB_ID] = fb_id
    _clear_pending_text(context)
    if already_subscribed:
        await update.effective_message.reply_text(
            "Спасибо, добавила в разбор. Вы уже подписаны на email-отчёт — "
            "пришлём 20 мая."
        )
    else:
        await update.effective_message.reply_text(
            "Спасибо, добавила в разбор. " + _email_pitch(),
            reply_markup=keyboards.followup_subscribe_keyboard(step),
        )
    return True


async def _subscribe_email(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, step: str, wants: bool
) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(
            session, telegram_id=update.effective_user.id
        )
        if wants:
            user.wants_followup_report = True
            await log_event(
                session,
                user_id=user.id,
                event="followup_report_optin",
                payload={"step": step},
            )
        await session.commit()

    if wants and not user.email:
        # Email FSM на стороне Чекапа — сюда не дублируем, чтобы текст
        # пользователя не попал в LLM-диалог по ошибке.
        await update.callback_query.message.reply_text(
            "Подписала. Email привяжется автоматически, когда вы оформите "
            "Чекап (там есть шаг с email для чека). Или напишите Ивану "
            "напрямую — он добавит вас в список вручную: @lvanKhudyakov.\n\n"
            "20 мая пришлём один email: что починили, что добавили по "
            "вашим ОС."
        )
    elif wants:
        await update.callback_query.message.reply_text(
            f"Подписала на {user.email}. 20 мая пришлём один email: "
            "что починили, что добавили по вашим ОС."
        )
    else:
        await update.callback_query.message.reply_text(
            "Окей, без рассылки. Спасибо за обратную связь!"
        )
    _clear(context)


async def _quick_praise_ai(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, message_log_id: str
) -> None:
    """Быстрый praise под ответом AI без комментария."""
    user_id = await _user_id_from_update(update)
    factory = async_session_factory()
    async with factory() as session:
        await record_feedback(
            session,
            user_id=user_id,
            step="ai_reply",
            category="praise",
            comment=f"message_log_id={message_log_id}",
        )
        await session.commit()
    try:
        await update.callback_query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await update.callback_query.message.reply_text(
        "Спасибо, что отметили — это помогает понять, что работает."
    )


async def _user_id_from_update(update: Update) -> int | None:
    if not update.effective_user:
        return None
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(
            session, telegram_id=update.effective_user.id
        )
        await session.commit()
        return user.id


def _clear(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(_FB_STEP, None)
    context.user_data.pop(_FB_CAT, None)
    context.user_data.pop(_FB_ID, None)


def _clear_pending_text(context: ContextTypes.DEFAULT_TYPE) -> None:
    # Шаг записан, FSM текстового ввода больше не ждём.
    context.user_data.pop(_FB_STEP, None)
    context.user_data.pop(_FB_CAT, None)


def _email_pitch() -> str:
    return (
        "Бета идёт 12–19 мая, после неё пришлём отчёт «что мы сделали по вашим ОС». "
        "Подпишетесь?"
    )


# ───────────────────────────── ADMIN ─────────────────────────────


async def feedback_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """`/feedback` — пагинация unresolved | `/feedback export` — md."""
    tg_id = update.effective_user.id
    if not is_admin(tg_id):
        await update.effective_message.reply_text(
            "Эта команда — только для команды EDL."
        )
        return
    args = context.args or []
    if args and args[0] == "export":
        await _admin_export(update)
        return
    await _admin_list(update, page=0)


async def _admin_list(update: Update, *, page: int) -> None:
    offset = page * _PAGE_SIZE
    factory = async_session_factory()
    async with factory() as session:
        stmt_all = select(Feedback).where(Feedback.reviewed_at.is_(None))
        all_rows = (await session.execute(stmt_all)).scalars().all()
        total = len(all_rows)

        stmt = (
            select(Feedback, User.telegram_username)
            .join(User, Feedback.user_id == User.id, isouter=True)
            .where(Feedback.reviewed_at.is_(None))
            .order_by(Feedback.reported_at.desc())
            .offset(offset)
            .limit(_PAGE_SIZE)
        )
        rows = (await session.execute(stmt)).all()

    if not rows:
        text = (
            "🎉 Неразобранной обратной связи нет."
            if page == 0
            else "Больше нет страниц. Возврат: /feedback"
        )
        await update.effective_message.reply_text(text)
        return

    await update.effective_message.reply_text(
        f"📨 *Feedback* (неразобранных: {total})\n"
        f"Страница {page + 1} · показано {len(rows)} из {total}",
        parse_mode=ParseMode.MARKDOWN,
    )

    for fb, username in rows:
        when = fb.reported_at.strftime("%d.%m %H:%M") if fb.reported_at else "—"
        user_part = f"@{username}" if username else f"user_id={fb.user_id}"
        cat_label = CATEGORIES.get(fb.category, fb.category)
        comment = (fb.comment or "—").strip()[:600].replace("*", "·").replace("_", "·")
        msg = (
            f"*FB #{fb.id}* · {when} · {user_part}\n"
            f"Шаг: `{fb.step}` · {cat_label}\n\n"
            f"_{comment}_"
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Решено", callback_data=f"feedback:review:resolve:{fb.id}"
                    ),
                    InlineKeyboardButton(
                        "🔧 В патч", callback_data=f"feedback:review:patched:{fb.id}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "❌ Игнор", callback_data=f"feedback:review:ignore:{fb.id}"
                    )
                ],
            ]
        )
        await update.effective_message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )

    if total > offset + len(rows):
        await update.effective_message.reply_text(
            "Дальше:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"→ Следующие {_PAGE_SIZE}",
                            callback_data=f"feedback:review:page:{page + 1}",
                        )
                    ]
                ]
            ),
        )


async def _admin_export(update: Update) -> None:
    factory = async_session_factory()
    async with factory() as session:
        stmt = (
            select(Feedback, User.telegram_username)
            .join(User, Feedback.user_id == User.id, isouter=True)
            .where(Feedback.reviewed_at.is_(None))
            .order_by(Feedback.reported_at.desc())
            .limit(100)
        )
        rows = (await session.execute(stmt)).all()

    if not rows:
        await update.effective_message.reply_text(
            "🎉 Нечего экспортировать — feedback разобран."
        )
        return

    lines = [
        f"# Feedback export · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Неразобранных: {len(rows)}",
        "",
    ]
    for fb, username in rows:
        when = fb.reported_at.strftime("%Y-%m-%d %H:%M") if fb.reported_at else "—"
        user_part = f"@{username}" if username else f"user_id={fb.user_id}"
        cat_label = CATEGORIES.get(fb.category, fb.category)
        lines.append(
            f"## FB #{fb.id} · {when} · {user_part} · `{fb.step}` · {cat_label}"
        )
        lines.append("")
        lines.append((fb.comment or "—").strip()[:800])
        lines.append("")

    md = "\n".join(lines)
    if len(md) > 3800:
        md = md[:3800] + "\n\n... (обрезано — см. /feedback по странице)"
    await update.effective_message.reply_text(
        md, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )


async def _review_callback(update: Update, parts: list[str]) -> None:
    """parts: ['resolve'|'patched'|'ignore'|'page', '<id или N>']."""
    if not is_admin(update.effective_user.id):
        return
    if len(parts) < 2:
        return
    action = parts[0]
    if action == "page":
        try:
            page = int(parts[1])
        except ValueError:
            return
        await _admin_list(update, page=page)
        return

    try:
        fb_id = int(parts[1])
    except ValueError:
        return
    resolution_map = {
        "resolve": ("✅ Решено", "resolved"),
        "patched": ("🔧 В патч", "patched"),
        "ignore": ("❌ Игнор", "ignored"),
    }
    if action not in resolution_map:
        return
    label, resolution_str = resolution_map[action]

    factory = async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(select(Feedback).where(Feedback.id == fb_id))
        ).scalar_one_or_none()
        if row is None:
            await update.callback_query.message.reply_text(f"FB #{fb_id} не найден.")
            return
        row.reviewed_by = str(update.effective_user.id)
        row.reviewed_at = datetime.now(timezone.utc)
        row.resolution = resolution_str
        await session.commit()

    try:
        await update.callback_query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await update.callback_query.message.reply_text(
        f"{label} · FB #{fb_id} помечен."
    )


# ───────────────────────────── WAITLIST ─────────────────────────────


async def handle_waitlist_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback `waitlist:join:<slot>` — фиксируем интерес к нерабочей фиче."""
    query = update.callback_query
    await query.answer()
    data = (query.data or "").split(":")
    if len(data) < 3:
        return
    slot = data[2]

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(
            session, telegram_id=update.effective_user.id
        )
        await log_event(
            session,
            user_id=user.id,
            event="waitlist_join",
            payload={"slot": slot},
        )
        await session.commit()

    labels = {
        "video_review": "видео-разбор Кати",
        "calendly": "автозапись в календарь",
        "audit_pdf": "PDF-пример отчёта",
    }
    label = labels.get(slot, slot)
    await query.message.reply_text(
        f"Записала: {label}. Откроем после 19 мая — Иван напишет лично.\n"
        f"Если срочно — @lvanKhudyakov."
    )
