"""/checkup — FSM прохождения 20 вопросов Бизнес-чекапа после оплаты."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot import texts
from src.core.checkup_questions import CHECKUP_QUESTIONS, CheckupQuestion, by_layer
from src.core.config import settings
from src.core.input_validation import InputValidationError, validate_user_text
from src.core.notifications import send_to_admin_chat
from src.db.models import Application, CheckupAnswer
from src.db.repos import get_or_create_user, log_event
from src.db.session import async_session_factory
from src.tasks.generate_checkup_pdf import generate_checkup_pdf

logger = logging.getLogger(__name__)

# FSM keys
_KEY_STATE = "checkup_state"
_KEY_APP_ID = "checkup_app_id"
_KEY_Q_IDX = "checkup_q_idx"   # 0-based index текущего вопроса

_STATE_AWAIT_START = "await_start"
_STATE_AWAIT_READY = "await_ready"
_STATE_AWAIT_ANSWER = "await_answer"

_LAYERS_ORDER = ["strategy", "sales", "operations", "finance"]
_MAX_ANSWER_CHARS = 4000

# Порог качества — если < 16 пройдено, предупреждаем
_QUALITY_PASS_THRESHOLD = 16


def _safe_uuid(s: str | None) -> UUID | None:
    """Безопасный парс UUID из callback_data. None — если значение пустое
    или не парсится (защита от malformed callback / устаревшей клавиатуры).
    Без try-except здесь ValueError всплыл бы в _global_error_handler и
    пользователь получил бы «Что-то пошло не так на нашей стороне».
    """
    if not s:
        return None
    try:
        return UUID(s)
    except (ValueError, TypeError):
        return None


def _progress_bar(current: int, total: int = 20) -> str:
    filled = round(current / total * 10)
    return "█" * filled + "░" * (10 - filled)


def _question_header(q: CheckupQuestion) -> str:
    layer_emoji = {"strategy": "📍", "sales": "📈", "operations": "⚙️", "finance": "💰"}
    emoji = layer_emoji.get(q.layer, "❓")
    bar = _progress_bar(q.order - 1)
    return (
        f"{emoji} *Вопрос {q.order}/20* · {bar} {(q.order - 1) * 5}%\n\n"
        f"_{q.why_we_ask}_\n\n"
        f"*{q.text}*"
    )


def _example_message(q: CheckupQuestion) -> str:
    return f"💡 *Пример хорошего ответа:*\n\n`{q.example_good}`"


def _question_keyboard(q_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Готов отвечать", callback_data=f"checkup:ready:{q_key}")],
        [InlineKeyboardButton("⏭ Пропустить (без зачёта)", callback_data=f"checkup:skip:{q_key}")],
    ])


def _quality_check(text: str, q: CheckupQuestion) -> tuple[bool, list[str]]:
    """Возвращает (passed, missing_labels)."""
    words = text.split()
    word_count = len(words)
    has_digit = bool(re.search(r"\d", text))
    missing = []
    if word_count < q.min_words:
        missing.append(f"нужно ≥{q.min_words} слов (у вас {word_count})")
    if not has_digit:
        missing.append("нужна хотя бы одна цифра")
    return len(missing) == 0, missing


async def _get_paid_application(session, telegram_id: int) -> Application | None:
    """Первая незавершённая paid Application типа audit."""
    user, _ = await get_or_create_user(session, telegram_id=telegram_id)
    stmt = (
        select(Application)
        .where(Application.user_id == user.id)
        .where(Application.type == "audit")
        .where(Application.status == "paid")
        .where(Application.checkup_completed_at.is_(None))
        .order_by(Application.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _count_answered(session, application_id: UUID) -> int:
    from sqlalchemy import func
    count = await session.scalar(
        select(func.count(CheckupAnswer.id))
        .where(CheckupAnswer.application_id == application_id)
    )
    return count or 0


async def _get_answers(session, application_id: UUID) -> list[CheckupAnswer]:
    rows = (
        await session.execute(
            select(CheckupAnswer).where(CheckupAnswer.application_id == application_id)
        )
    ).scalars().all()
    return list(rows)


# ─── /checkup ─────────────────────────────────────────────────────────────────


async def checkup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message

    factory = async_session_factory()
    async with factory() as session:
        app = await _get_paid_application(session, user.id)
        if app is None:
            await msg.reply_text(
                texts.CHECKUP_NO_PAID_APP,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📋 Оформить Чекап", callback_data="menu:audit")]]
                ),
            )
            return

        answered = await _count_answered(session, app.id)
        plan = (app.payload or {}).get("plan", "base") if app.payload else "base"

    if answered > 0:
        # Показываем прогресс и спрашиваем: продолжить или заново
        bar = _progress_bar(answered)
        await msg.reply_text(
            f"Вы остановились на вопросе {answered}/20.\n{bar} {answered * 5}% готово.\n\n"
            "Продолжить с того места или начать заново?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Продолжить", callback_data=f"checkup:resume:{app.id}")],
                [InlineKeyboardButton("🔄 Начать заново (прогресс стирается)", callback_data=f"checkup:restart:{app.id}")],
            ]),
        )
        return

    # Новый запуск
    intro = texts.CHECKUP_INTRO_PLUS if plan == "plus" else texts.CHECKUP_INTRO_BASE
    await msg.reply_text(
        intro,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Начать", callback_data=f"checkup:start:{app.id}")],
        ]),
        disable_web_page_preview=True,
    )


# ─── Callbacks ────────────────────────────────────────────────────────────────


async def handle_checkup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    parts = data.split(":")

    action = parts[1] if len(parts) > 1 else ""

    if action == "start":
        app_id = parts[2] if len(parts) > 2 else None
        await _start_checkup(update, context, app_id)
    elif action == "resume":
        app_id = parts[2] if len(parts) > 2 else None
        await _resume_checkup(update, context, app_id)
    elif action == "restart":
        app_id = parts[2] if len(parts) > 2 else None
        await _restart_checkup(update, context, app_id)
    elif action == "ready":
        q_key = parts[2] if len(parts) > 2 else None
        await _set_ready_for_answer(update, context, q_key)
    elif action == "skip":
        q_key = parts[2] if len(parts) > 2 else None
        await _skip_question(update, context, q_key)
    elif action == "keep":
        await _keep_answer(update, context)
    elif action == "improve":
        await _ask_improve(update, context)
    elif action == "submit":
        app_id = parts[2] if len(parts) > 2 else None
        await _submit_checkup(update, context, app_id)


async def _start_checkup(update: Update, context: ContextTypes.DEFAULT_TYPE, app_id_str: str | None) -> None:
    if not app_id_str:
        return
    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return
    factory = async_session_factory()
    async with factory() as session:
        app = await session.get(Application, app_uuid)
        if app is None:
            return
        app.checkup_started_at = datetime.now(timezone.utc)
        await session.commit()

    context.user_data[_KEY_APP_ID] = app_id_str
    context.user_data[_KEY_Q_IDX] = 0
    context.user_data[_KEY_STATE] = _STATE_AWAIT_READY
    await _send_question(update, context, 0)


async def _resume_checkup(update: Update, context: ContextTypes.DEFAULT_TYPE, app_id_str: str | None) -> None:
    if not app_id_str:
        return
    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return
    answered_keys: set[str] = set()
    factory = async_session_factory()
    async with factory() as session:
        answers = await _get_answers(session, app_uuid)
        answered_keys = {a.question_key for a in answers}

    # Находим первый незаданный вопрос
    next_idx = 0
    for i, q in enumerate(CHECKUP_QUESTIONS):
        if q.key not in answered_keys:
            next_idx = i
            break
    else:
        next_idx = len(CHECKUP_QUESTIONS)

    context.user_data[_KEY_APP_ID] = app_id_str
    context.user_data[_KEY_Q_IDX] = next_idx
    context.user_data[_KEY_STATE] = _STATE_AWAIT_READY

    if next_idx >= len(CHECKUP_QUESTIONS):
        await _finalize_checkup(update, context, app_id_str)
    else:
        await _send_question(update, context, next_idx)


async def _restart_checkup(update: Update, context: ContextTypes.DEFAULT_TYPE, app_id_str: str | None) -> None:
    if not app_id_str:
        return
    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return
    factory = async_session_factory()
    async with factory() as session:
        # Удаляем все ответы
        answers = await _get_answers(session, app_uuid)
        for a in answers:
            await session.delete(a)
        app = await session.get(Application, app_uuid)
        if app:
            app.checkup_started_at = datetime.now(timezone.utc)
            app.checkup_completed_at = None
        await session.commit()

    context.user_data[_KEY_APP_ID] = app_id_str
    context.user_data[_KEY_Q_IDX] = 0
    context.user_data[_KEY_STATE] = _STATE_AWAIT_READY
    await _send_question(update, context, 0)


async def _send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, q_idx: int) -> None:
    msg = update.effective_message or update.callback_query.message
    q = CHECKUP_QUESTIONS[q_idx]

    # Вставляем layer intro если первый вопрос слоя
    layer_orders = {"strategy": 0, "sales": 5, "operations": 10, "finance": 15}
    if q.order - 1 == layer_orders.get(q.layer, -1):
        await msg.reply_text(
            texts.CHECKUP_LAYER_INTRO[q.layer],
            parse_mode="Markdown",
        )

    await msg.reply_text(_question_header(q), parse_mode="Markdown")
    await msg.reply_text(_example_message(q), parse_mode="Markdown", reply_markup=_question_keyboard(q.key))


async def _set_ready_for_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, q_key: str | None) -> None:
    if not q_key:
        return
    context.user_data[_KEY_STATE] = _STATE_AWAIT_ANSWER
    # Храним ключ текущего вопроса
    for i, q in enumerate(CHECKUP_QUESTIONS):
        if q.key == q_key:
            context.user_data[_KEY_Q_IDX] = i
            break
    await update.callback_query.message.reply_text(
        "✍️ Жду ваш ответ одним сообщением. Не торопитесь — прогресс сохраняется."
    )


async def _skip_question(update: Update, context: ContextTypes.DEFAULT_TYPE, q_key: str | None) -> None:
    if not q_key:
        return
    app_id_str = context.user_data.get(_KEY_APP_ID)
    if not app_id_str:
        return

    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return
    q = next((x for x in CHECKUP_QUESTIONS if x.key == q_key), None)
    if q is None:
        return

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        existing = (
            await session.execute(
                select(CheckupAnswer)
                .where(CheckupAnswer.application_id == app_uuid)
                .where(CheckupAnswer.question_key == q_key)
            )
        ).scalar_one_or_none()

        if existing is None:
            session.add(CheckupAnswer(
                application_id=app_uuid,
                user_id=user.id,
                question_key=q_key,
                layer=q.layer,
                text="[пропущено]",
                word_count=0,
                quality_passed=False,
                quality_notes=json.dumps(["вопрос пропущен"], ensure_ascii=False),
            ))
        await log_event(session, user_id=user.id, event="checkup_question_skipped", payload={"q": q_key})
        await session.commit()

    await update.callback_query.message.reply_text(f"Пропускаем вопрос {q.order}/20 (без зачёта).")
    await _advance_to_next(update, context, q.order - 1 + 1)


async def _advance_to_next(update: Update, context: ContextTypes.DEFAULT_TYPE, next_idx: int) -> None:
    context.user_data[_KEY_Q_IDX] = next_idx
    context.user_data[_KEY_STATE] = _STATE_AWAIT_READY

    if next_idx >= len(CHECKUP_QUESTIONS):
        app_id_str = context.user_data.get(_KEY_APP_ID)
        await _finalize_checkup(update, context, app_id_str)
    else:
        await _send_question(update, context, next_idx)


async def _keep_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Юзер решил оставить короткий ответ как есть."""
    q_idx = context.user_data.get(_KEY_Q_IDX, 0)
    await _advance_to_next(update, context, q_idx + 1)


async def _ask_improve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Юзер хочет дополнить ответ."""
    context.user_data[_KEY_STATE] = _STATE_AWAIT_ANSWER
    await update.callback_query.message.reply_text("Дополните ответ одним сообщением:")


async def _finalize_checkup(
    update: Update, context: ContextTypes.DEFAULT_TYPE, app_id_str: str | None
) -> None:
    if not app_id_str:
        return
    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return
    msg = update.effective_message or (update.callback_query.message if update.callback_query else None)

    factory = async_session_factory()
    async with factory() as session:
        answers = await _get_answers(session, app_uuid)
        passed = sum(1 for a in answers if a.quality_passed)
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)

        if passed < _QUALITY_PASS_THRESHOLD:
            # Показываем предупреждение
            weak = [a.question_key for a in answers if not a.quality_passed and a.text != "[пропущено]"]
            weak_str = ", ".join(weak[:5])
            if msg:
                await msg.reply_text(
                    f"⚠️ {passed} из 20 ответов прошли рубрику. "
                    f"Слабые пункты: {weak_str}.\n\n"
                    "Можно вернуться и дополнить, или отправить как есть "
                    "(разбор по этим пунктам будет в режиме «гипотезы»).",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            f"📨 Отправить как есть ({passed}/20 зачтено)",
                            callback_data=f"checkup:submit:{app_id_str}"
                        )],
                    ]),
                )
                return  # Не завершаем сразу — ждём нажатия кнопки

        await _do_complete(session, app_uuid, user, passed, msg, app_id_str, context)


async def _submit_checkup(update: Update, context: ContextTypes.DEFAULT_TYPE, app_id_str: str | None) -> None:
    """Юзер нажал «Отправить как есть» при < порога quality."""
    if not app_id_str:
        return
    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return
    factory = async_session_factory()
    async with factory() as session:
        answers = await _get_answers(session, app_uuid)
        passed = sum(1 for a in answers if a.quality_passed)
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        msg = update.callback_query.message
        await _do_complete(session, app_uuid, user, passed, msg, app_id_str, context)


async def _do_complete(session, app_uuid, user, passed, msg, app_id_str, context) -> None:
    app = await session.get(Application, app_uuid)
    if app:
        app.checkup_completed_at = datetime.now(timezone.utc)
    await log_event(
        session, user_id=user.id, event="checkup_completed",
        payload={"application_id": str(app_uuid), "quality_passed": passed},
    )
    await session.commit()

    if msg:
        await msg.reply_text(
            f"🎉 Чекап завершён! {passed}/20 ответов прошли рубрику.\n\n"
            "Генерирую PDF-черновик. Пришлю его в этот чат — займёт несколько минут.\n\n"
            f"Условия услуги: {settings.offer_checkup_url}"
        )

    # Запускаем генерацию PDF в фоне
    try:
        generate_checkup_pdf.delay(str(app_uuid))
    except Exception:
        logger.exception("Failed to trigger generate_checkup_pdf for %s", app_uuid)

    # Бриф в admin_chat
    try:
        brief = (
            f"✅ Чекап завершён\n"
            f"Application: {app_uuid}\n"
            f"User: @{user.telegram_username or user.telegram_id}\n"
            f"Качество: {passed}/20 ответов прошли рубрику\n"
            f"PDF-черновик генерируется — ждёт ревью Кати."
        )
        if context and hasattr(context, "bot"):
            await send_to_admin_chat(context.bot, brief)
    except Exception:
        logger.exception("Failed to send admin brief for checkup %s", app_uuid)

    # Очищаем FSM
    for key in [_KEY_STATE, _KEY_APP_ID, _KEY_Q_IDX]:
        context.user_data.pop(key, None)


# ─── Text handler (FSM step) ──────────────────────────────────────────────────


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обрабатывает ответ на текущий вопрос Чекапа. Возвращает True если обработал."""
    state = context.user_data.get(_KEY_STATE)
    if state != _STATE_AWAIT_ANSWER:
        return False

    app_id_str = context.user_data.get(_KEY_APP_ID)
    q_idx = context.user_data.get(_KEY_Q_IDX, 0)
    if not app_id_str or q_idx >= len(CHECKUP_QUESTIONS):
        return False

    try:
        raw = validate_user_text((update.effective_message.text or "").strip())
    except InputValidationError as e:
        await update.effective_message.reply_text(str(e))
        return True

    # Обрезаем до лимита
    if len(raw) > _MAX_ANSWER_CHARS:
        raw = raw[:_MAX_ANSWER_CHARS]

    q = CHECKUP_QUESTIONS[q_idx]
    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return
    passed, missing = _quality_check(raw, q)
    word_count = len(raw.split())

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)

        # Upsert ответа
        existing = (
            await session.execute(
                select(CheckupAnswer)
                .where(CheckupAnswer.application_id == app_uuid)
                .where(CheckupAnswer.question_key == q.key)
            )
        ).scalar_one_or_none()

        if existing:
            existing.text = raw
            existing.word_count = word_count
            existing.quality_passed = passed
            existing.quality_notes = json.dumps(missing, ensure_ascii=False) if missing else None
        else:
            session.add(CheckupAnswer(
                application_id=app_uuid,
                user_id=user.id,
                question_key=q.key,
                layer=q.layer,
                text=raw,
                word_count=word_count,
                quality_passed=passed,
                quality_notes=json.dumps(missing, ensure_ascii=False) if missing else None,
            ))
        await log_event(session, user_id=user.id, event="checkup_answer_saved", payload={"q": q.key, "passed": passed})
        # F7: обновляем persistent progress
        app = await session.get(Application, app_uuid)
        if app is not None:
            if hasattr(app, "checkup_current_question_index"):
                app.checkup_current_question_index = q_idx + 1
            if hasattr(app, "checkup_last_active_at"):
                app.checkup_last_active_at = datetime.now(timezone.utc)
        await session.commit()

    if not passed:
        missing_str = "; ".join(missing)
        await update.effective_message.reply_text(
            f"В этом ответе: {missing_str}.\n\n"
            "Можно дополнить одним сообщением, или оставить как есть.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Дополнить", callback_data="checkup:improve")],
                [InlineKeyboardButton("👌 Оставить так", callback_data="checkup:keep")],
            ]),
        )
        return True

    # Ответ принят
    bar = _progress_bar(q.order)
    await update.effective_message.reply_text(
        f"✅ Принято. Вопрос {q.order}/20. {bar} {q.order * 5}%"
    )
    await _advance_to_next(update, context, q_idx + 1)
    return True


# ─── F7: Pause/Resume helpers ─────────────────────────────────────────────────


def is_in_checkup_fsm(user_data: dict) -> bool:
    """True если пользователь сейчас активно проходит чекап."""
    return bool(user_data.get(_KEY_STATE) and user_data.get(_KEY_APP_ID))


async def get_paused_checkup(telegram_id: int) -> Application | None:
    """Возвращает незавершённую Application если есть пауза > 30 минут.

    Используется в dialog.py для реактивного предложения продолжить.
    """
    from datetime import timedelta

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=telegram_id)
        stmt = (
            select(Application)
            .where(Application.user_id == user.id)
            .where(Application.type == "audit")
            .where(Application.status == "paid")
            .where(Application.checkup_completed_at.is_(None))
            .where(Application.checkup_started_at.isnot(None))
            .order_by(Application.created_at.desc())
            .limit(1)
        )
        app = (await session.execute(stmt)).scalar_one_or_none()
        if app is None:
            return None

        # Пауза > 30 минут?
        last_active = getattr(app, "checkup_last_active_at", None) or app.checkup_started_at
        if last_active is None:
            return None
        minutes_idle = (datetime.now(timezone.utc) - last_active).total_seconds() / 60
        if minutes_idle < 30:
            return None

        # Есть ли хотя бы один ответ (иначе чекап не начат)?
        answered = await _count_answered(session, app.id)
        return app if answered > 0 else None
