"""/bugs — команда для просмотра bug-report'ов от пользователей (§E.2 v3.1).

Только для админа. Показывает неразобранные баги с превью текста бота
и inline-кнопками для пометки. Пагинация по 5 штук.

Доп. команды:
- /bugs export — выгрузка всех unresolved в markdown в чат админа
  (можно переслать аналитику или мне для разбора).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.admin.auth import is_admin
from src.db.models import BotError, MessageLog, User
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

# Сколько багов показываем за раз
_PAGE_SIZE = 5


async def bugs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/bugs` — список неразобранных багов | `/bugs export` — выгрузка md."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.effective_message.reply_text(
            "Эта команда — только для команды EDL."
        )
        return

    args = (context.args or [])
    if args and args[0] == "export":
        await _bugs_export(update)
        return

    await _bugs_list(update, page=0)


async def _bugs_list(update: Update, *, page: int = 0) -> None:
    """Покажет страницу неразобранных багов."""
    offset = page * _PAGE_SIZE
    factory = async_session_factory()
    async with factory() as session:
        # Общее число unresolved
        total = await session.scalar(
            select(BotError).where(BotError.reviewed_at.is_(None)).with_only_columns(
                BotError.id
            )
        )
        # Запрос пачки с превью текста бота
        stmt = (
            select(BotError, MessageLog.text, User.telegram_username)
            .join(MessageLog, BotError.message_log_id == MessageLog.id, isouter=True)
            .join(User, BotError.user_id == User.id, isouter=True)
            .where(BotError.reviewed_at.is_(None))
            .order_by(BotError.reported_at.desc())
            .offset(offset)
            .limit(_PAGE_SIZE)
        )
        rows = (await session.execute(stmt)).all()

        # Общее число для отображения «X / N»
        count_stmt = (
            select(BotError)
            .where(BotError.reviewed_at.is_(None))
        )
        all_unresolved = (await session.execute(count_stmt)).scalars().all()
        total_count = len(all_unresolved)

    if not rows:
        if page == 0:
            await update.effective_message.reply_text(
                "🎉 Неразобранных багов нет. Канал чистый."
            )
        else:
            await update.effective_message.reply_text(
                "Больше нет страниц. Возврат на первую: /bugs"
            )
        return

    header = (
        f"📋 *Bug-reports* (неразобранных: {total_count})\n"
        f"Страница {page + 1} · показано {len(rows)} из {total_count}\n\n"
    )

    # Шлём header + одно сообщение на каждый баг (чтобы кнопки были рядом)
    await update.effective_message.reply_text(header, parse_mode=ParseMode.MARKDOWN)

    for err, bot_text, username in rows:
        when = err.reported_at.strftime("%d.%m %H:%M") if err.reported_at else "—"
        preview = (bot_text or "—")[:400].replace("*", "·").replace("_", "·")
        comment = (err.user_comment or "").strip()
        user_part = f"@{username}" if username else f"user_id={err.user_id}"

        text = (
            f"*Bug #{err.id}* · {when} · {user_part}\n\n"
            f"*Ответ бота, который пометили:*\n```\n{preview}\n```\n"
        )
        if comment:
            text += f"\n*Комментарий пользователя:*\n_{comment[:300]}_\n"

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Решено", callback_data=f"bug:resolve:{err.id}"),
                    InlineKeyboardButton("🔧 Запатчили", callback_data=f"bug:patched:{err.id}"),
                ],
                [
                    InlineKeyboardButton("❌ Игнор (не баг)", callback_data=f"bug:ignore:{err.id}"),
                ],
            ]
        )
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )

    # Пагинация если есть ещё
    if total_count > offset + len(rows):
        next_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                f"→ Следующие 5 ({total_count - (offset + len(rows))} осталось)",
                callback_data=f"bug:page:{page + 1}",
            )]]
        )
        await update.effective_message.reply_text(
            "Дальше:", reply_markup=next_kb
        )


async def _bugs_export(update: Update) -> None:
    """Выгрузка ВСЕХ unresolved багов в md-формате одним сообщением.

    Удобно: переслать в чат с разработчиком (со мной) для batch-разбора.
    """
    factory = async_session_factory()
    async with factory() as session:
        stmt = (
            select(BotError, MessageLog.text, User.telegram_username)
            .join(MessageLog, BotError.message_log_id == MessageLog.id, isouter=True)
            .join(User, BotError.user_id == User.id, isouter=True)
            .where(BotError.reviewed_at.is_(None))
            .order_by(BotError.reported_at.desc())
            .limit(100)
        )
        rows = (await session.execute(stmt)).all()

    if not rows:
        await update.effective_message.reply_text(
            "🎉 Нечего экспортировать — все баги разобраны."
        )
        return

    lines = [
        f"# Bug-bucket export · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Неразобранных: {len(rows)}",
        "",
    ]
    for err, bot_text, username in rows:
        when = err.reported_at.strftime("%Y-%m-%d %H:%M") if err.reported_at else "—"
        user_part = f"@{username}" if username else f"user_id={err.user_id}"
        comment = (err.user_comment or "").strip()
        preview = (bot_text or "—")[:600]
        lines.append(f"## Bug #{err.id} · {when} · {user_part}")
        lines.append("")
        lines.append("**Ответ бота:**")
        lines.append("```")
        lines.append(preview)
        lines.append("```")
        if comment:
            lines.append(f"**Комментарий:** {comment[:300]}")
        lines.append("")

    md = "\n".join(lines)
    # Telegram limit ~4000 символов — режем если надо
    if len(md) > 3800:
        md = md[:3800] + "\n\n... (обрезано — посмотри /bugs для просмотра по странице)"

    await update.effective_message.reply_text(
        md, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
    )


async def handle_bug_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback: bug:resolve:N | bug:patched:N | bug:ignore:N | bug:page:N."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    data = (query.data or "").split(":")
    if len(data) < 3 and data[1] != "page":
        return
    action = data[1]

    if action == "page":
        page = int(data[2])
        await _bugs_list(update, page=page)
        return

    bug_id = int(data[2])
    resolution_map = {
        "resolve": ("✅ Решено", "resolved", False),
        "patched": ("🔧 Запатчили", "prompt_patched", True),
        "ignore": ("❌ Игнор", "ignored_not_a_bug", False),
    }
    if action not in resolution_map:
        return
    label, resolution_str, prompt_patched_flag = resolution_map[action]

    factory = async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(select(BotError).where(BotError.id == bug_id))
        ).scalar_one_or_none()
        if row is None:
            await query.message.reply_text(f"Bug #{bug_id} не найден.")
            return
        row.reviewed_by = str(user_id)
        row.reviewed_at = datetime.now(timezone.utc)
        row.resolution = resolution_str
        row.prompt_patched = prompt_patched_flag
        await session.commit()

    # Обновляем оригинальное сообщение чтобы показать что отмечено
    try:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"{label} · Bug #{bug_id} помечен."
        )
    except Exception:
        logger.exception("Failed to update bug message")
