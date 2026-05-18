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
_STATE_AWAIT_SCALE = "await_scale"  # HOT-fix 19.05: pre-flight размер компании
_STATE_AWAIT_READY = "await_ready"
_STATE_AWAIT_ANSWER = "await_answer"
# 21-й уточняющий вопрос — 3 ключевые метрики бизнеса.
# Не нумеруем как «21/21» — методологически Founder OS = 20 вопросов,
# приоритеты — финальный штрих для персонализации сценариев в PDF.
_STATE_AWAIT_PRIORITIES = "await_priorities"
_STATE_AWAIT_PRIORITIES_RETRY = "await_priorities_retry"

# HOT-fix 19.05: размер компании влияет на смягчение порогов и формулировки.
SCALE_MICRO = "micro"      # 1-5 человек, оборот <10М/год
SCALE_SMALL = "small"      # 6-20 человек, оборот 10-50М/год
SCALE_MEDIUM = "medium"    # 21-50 человек, оборот >50М/год
SCALE_LABELS = {
    SCALE_MICRO: "Микро · 1-5 чел.",
    SCALE_SMALL: "Малый · 6-20 чел.",
    SCALE_MEDIUM: "Средний · 21-50 чел.",
}

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


# «Не применимо для масштаба» — клиент явно сказал, что у него нет таких
# данных (микро-бизнес, услуги без проектной маржи и т.п.). Засчитываем
# ответ как corner case — quality_passed=True, чтобы не блокировать
# завершение Чекапа, в PDF используем формулировку «клиент не считает».
_NOT_APPLICABLE_MARKERS = (
    "не считаю", "не считаем", "не применимо",
    "нет данных", "не релевантно", "не релевантна",
    "не веду", "не ведём", "не отслеживаю", "не отслеживаем",
)


def _is_not_applicable(text: str) -> bool:
    t = (text or "").lower()
    return any(marker in t for marker in _NOT_APPLICABLE_MARKERS)


_FINANCE_QUESTIONS = {"m1_cashflow", "m2_ebitda", "m3_vat_2026", "m4_reserves",
                       "o2_project_margin"}


def _scale_multiplier(scale: str | None) -> float:
    """Микро-бизнес отвечает короче — снижаем порог слов на 40%."""
    if scale == SCALE_MICRO:
        return 0.6
    if scale == SCALE_SMALL:
        return 0.8
    return 1.0


def _quality_check(text: str, q: CheckupQuestion, scale: str | None = None) -> tuple[bool, list[str]]:
    """Возвращает (passed, missing_labels). Адаптивно по размеру компании."""
    # Если клиент явно сказал «не считаю/не применимо» — для финвопросов
    # засчитываем (микро/малые часто не ведут finmodel) и помечаем флагом.
    if _is_not_applicable(text) and q.key in _FINANCE_QUESTIONS:
        return True, ["не применимо для масштаба — учтено"]

    words = text.split()
    word_count = len(words)
    has_digit = bool(re.search(r"\d", text))

    effective_min = max(8, int(q.min_words * _scale_multiplier(scale)))
    missing = []
    if word_count < effective_min:
        missing.append(f"нужно ≥{effective_min} слов (у вас {word_count})")
    # Для микро не требуем цифру в нефинансовых вопросах
    finance_q = q.key in _FINANCE_QUESTIONS
    if not has_digit and (finance_q or scale != SCALE_MICRO):
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
    elif action == "scale":
        # checkup:scale:<micro|small|medium>:<app_id>
        scale = parts[2] if len(parts) > 2 else None
        app_id = parts[3] if len(parts) > 3 else None
        if scale and app_id:
            await _handle_scale_choice(update, context, scale, app_id)
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
    """Pre-flight: спрашиваем размер компании, чтобы адаптировать формулировки
    и пороги качества под микро/малый/средний.
    """
    if not app_id_str:
        return
    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return

    # Если scale уже выбран (resume сценарий) — пропускаем pre-flight
    factory = async_session_factory()
    async with factory() as session:
        app = await session.get(Application, app_uuid)
        if app is None:
            return
        existing_scale = (app.payload or {}).get("company_scale")

    if existing_scale:
        # Resume — сразу к первому вопросу
        async with factory() as session:
            app = await session.get(Application, app_uuid)
            if app:
                app.checkup_started_at = datetime.now(timezone.utc)
                await session.commit()
        context.user_data[_KEY_APP_ID] = app_id_str
        context.user_data[_KEY_Q_IDX] = 0
        context.user_data[_KEY_STATE] = _STATE_AWAIT_READY
        await _send_question(update, context, 0)
        return

    # Pre-flight scale
    context.user_data[_KEY_APP_ID] = app_id_str
    context.user_data[_KEY_STATE] = _STATE_AWAIT_SCALE
    msg = update.effective_message or (update.callback_query.message if update.callback_query else None)
    if msg is None:
        return
    await msg.reply_text(
        "Перед стартом — *размер вашей команды*?\n\n"
        "Это поможет мне приземлить вопросы под ваш масштаб. "
        "Часть вопросов про маржу/EBITDA/cash-flow для микро-команды "
        "формулируется проще.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Микро · 1-5 чел.", callback_data=f"checkup:scale:micro:{app_id_str}")],
            [InlineKeyboardButton("Малый · 6-20 чел.", callback_data=f"checkup:scale:small:{app_id_str}")],
            [InlineKeyboardButton("Средний · 21-50 чел.", callback_data=f"checkup:scale:medium:{app_id_str}")],
        ]),
    )


async def _handle_scale_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE, scale: str, app_id_str: str
) -> None:
    """Колбэк checkup:scale:<scale>:<app_id> — сохраняем scale и запускаем 20 вопросов."""
    if scale not in (SCALE_MICRO, SCALE_SMALL, SCALE_MEDIUM):
        return
    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return
    factory = async_session_factory()
    async with factory() as session:
        app = await session.get(Application, app_uuid)
        if app is None:
            return
        payload = dict(app.payload or {})
        payload["company_scale"] = scale
        app.payload = payload
        app.checkup_started_at = datetime.now(timezone.utc)
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(
            session, user_id=user.id, event="checkup_scale_chosen",
            payload={"application_id": app_id_str, "scale": scale},
        )
        await session.commit()

    context.user_data[_KEY_APP_ID] = app_id_str
    context.user_data[_KEY_Q_IDX] = 0
    context.user_data[_KEY_STATE] = _STATE_AWAIT_READY

    msg = update.effective_message or update.callback_query.message
    if msg:
        await msg.reply_text(
            f"Принято — {SCALE_LABELS[scale]}. Стартуем 20 вопросов по 4 слоям.\n\n"
            "На каждый вопрос есть пример хорошего ответа. Если вопрос не "
            "релевантен для вашего масштаба — напишите «не считаю» и одну "
            "причину, я это учту в PDF."
        )
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

        # 21-й уточняющий вопрос (priority_metrics) перед _do_complete.
        await _ask_priorities(update, context, app_id_str)


async def _submit_checkup(update: Update, context: ContextTypes.DEFAULT_TYPE, app_id_str: str | None) -> None:
    """Юзер нажал «Отправить как есть» при < порога quality."""
    if not app_id_str:
        return
    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return
    await _ask_priorities(update, context, app_id_str)


# ─── 21-й уточняющий вопрос: priority_metrics ─────────────────────────────────


async def _ask_priorities(
    update: Update, context: ContextTypes.DEFAULT_TYPE, app_id_str: str
) -> None:
    """Спрашиваем 3 ключевые метрики бизнеса перед формированием PDF."""
    from src.core.priority_metrics import PROMPT_TEXT

    msg = update.effective_message or (update.callback_query.message if update.callback_query else None)
    if msg is None:
        return
    context.user_data[_KEY_APP_ID] = app_id_str
    context.user_data[_KEY_STATE] = _STATE_AWAIT_PRIORITIES
    await msg.reply_text(PROMPT_TEXT, parse_mode="Markdown")


async def _handle_priorities_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str
) -> bool:
    """Обрабатывает ответ на 21-й вопрос. Возвращает True если шаг закрыт.

    Логика:
    - parse → validate
    - too_few → переспросить один раз
    - too_many → попросить выбрать топ-3
    - not_metrics на первом проходе → retry (мягко)
    - not_metrics на retry → принять как есть с пометкой soft_match=false
    - ok → сохранить и перейти к _do_complete
    """
    from src.core.priority_metrics import parse_metrics, validate_metrics

    app_id_str = context.user_data.get(_KEY_APP_ID)
    if not app_id_str:
        return False
    app_uuid = _safe_uuid(app_id_str)
    if app_uuid is None:
        return False

    state = context.user_data.get(_KEY_STATE)
    is_retry = state == _STATE_AWAIT_PRIORITIES_RETRY

    metrics = parse_metrics(raw)
    status, normalized = validate_metrics(metrics)

    msg = update.effective_message

    if status == "too_few":
        await msg.reply_text(
            "Нужно минимум 2 метрики. Назовите хотя бы 2 — третью можете "
            "пропустить, если затрудняетесь."
        )
        return True

    if status == "too_many":
        await msg.reply_text(
            f"Я насчитала {len(metrics)} метрик — для сценариев важна "
            "приоритизация. Выберите топ-3 в порядке приоритета."
        )
        return True

    if status == "not_metrics" and not is_retry:
        from src.core.priority_metrics import RETRY_TEXT
        context.user_data[_KEY_STATE] = _STATE_AWAIT_PRIORITIES_RETRY
        await msg.reply_text(RETRY_TEXT)
        return True

    # ok ИЛИ not_metrics на retry — сохраняем и завершаем
    soft_match = status == "ok"

    factory = async_session_factory()
    async with factory() as session:
        app = await session.get(Application, app_uuid)
        if app is None:
            return False
        payload = dict(app.payload or {})
        payload["priority_metrics"] = normalized
        payload["priority_metrics_soft_match"] = soft_match
        app.payload = payload
        answers = await _get_answers(session, app_uuid)
        passed = sum(1 for a in answers if a.quality_passed)
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(
            session,
            user_id=user.id,
            event="checkup_priority_metrics_captured",
            payload={
                "application_id": app_id_str,
                "metrics": normalized,
                "soft_match": soft_match,
            },
        )
        await session.commit()
        await _do_complete(session, app_uuid, user, passed, msg, app_id_str, context)
    return True


async def _do_complete(session, app_uuid, user, passed, msg, app_id_str, context) -> None:
    app = await session.get(Application, app_uuid)
    if app:
        app.checkup_completed_at = datetime.now(timezone.utc)
    await log_event(
        session, user_id=user.id, event="checkup_completed",
        payload={"application_id": str(app_uuid), "quality_passed": passed},
    )
    await session.commit()

    plan = "base"
    is_self_demo = False
    if app:
        payload = app.payload or {}
        plan = payload.get("plan", "base")
        is_self_demo = bool(payload.get("is_self_demo"))

    if msg:
        rec_count = 7 if plan == "plus" else 5
        page_count = "12-15" if plan == "plus" else "10-12"
        plus_block = (
            (
                "\n*Plus-тариф*: PDF подробнее (≈12-15 стр., 7 рекомендаций), "
                "и через 24 часа после завершения Чекапа в этот чат придёт "
                "ваше персональное видео от Кати."
            )
            if plan == "plus" and not is_self_demo
            else ""
        )
        await msg.reply_text(
            f"🎉 Чекап завершён! {passed}/20 ответов прошли рубрику.\n\n"
            f"Готовлю PDF: диагноз по 4 слоям, {rec_count} конкретных "
            f"рекомендаций, 3 сценария под ваши приоритетные метрики. "
            f"Объём — около {page_count} страниц.\n\n"
            "⏱ *Время на генерацию — 3–7 минут.* Можете заварить чай — "
            "я пришлю PDF в этот чат, как только всё будет готово.\n"
            f"{plus_block}\n\n"
            f"Условия услуги: {settings.offer_checkup_url}",
            parse_mode="Markdown",
        )

    # Запускаем генерацию PDF: сначала inline (без зависимости от Celery
    # worker'а), параллельно — в очередь Celery как резерв. Inline создаёт
    # asyncio-таску — не блокирует ответ юзеру.
    # HOT-fix 19.05: на Railway Celery worker может быть не запущен —
    # PDF висел бесконечно в Redis-queue. Inline решает корневую причину.
    import asyncio
    from src.tasks.generate_checkup_pdf import _generate as _generate_pdf_inline

    async def _inline_pdf_with_fallback() -> None:
        try:
            await _generate_pdf_inline(str(app_uuid))
        except Exception:
            logger.exception("Inline PDF generation failed for %s", app_uuid)
            # Алерт Кате — клиент не получил PDF
            try:
                from src.core.notifications import send_to_admin_chat
                if context and hasattr(context, "bot"):
                    await send_to_admin_chat(
                        context.bot,
                        f"⚠️ PDF generation failed для {app_uuid}.\n"
                        f"User: @{user.telegram_username or user.telegram_id}\n"
                        f"Plan: {plan}\n"
                        "Запустить вручную: /regenerate_pdf "
                        f"{app_uuid}",
                    )
            except Exception:
                logger.exception("Failed to alert admin about PDF failure")

    asyncio.create_task(_inline_pdf_with_fallback())

    # Celery как резерв — если worker запущен, он подхватит и сделает идемпотентно
    try:
        generate_checkup_pdf.delay(str(app_uuid))
    except Exception:
        logger.debug("Celery enqueue skipped (worker likely not running)")

    # Plus-видео бриф Кате — триггерим от ЗАВЕРШЕНИЯ Чекапа, не от оплаты
    # (SoT v1.5 patch §2.3 шаг 2). Self-demo не триггерят бриф — иначе
    # бесконечный цикл для самотеста Кати.
    if plan == "plus" and not is_self_demo:
        try:
            from src.tasks.notify_plus_video import schedule_plus_video_brief
            schedule_plus_video_brief.delay(str(app_uuid))
        except Exception:
            logger.exception("Failed to schedule plus video brief for %s", app_uuid)

    # Бриф в admin_chat
    try:
        demo_tag = " · self-demo" if is_self_demo else ""
        brief = (
            f"✅ Чекап завершён{demo_tag}\n"
            f"Application: {app_uuid}\n"
            f"User: @{user.telegram_username or user.telegram_id}\n"
            f"Plan: {plan}\n"
            f"Качество: {passed}/20 ответов прошли рубрику\n"
            f"PDF генерируется автоматически и отправляется клиенту."
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

    # 21-й вопрос (priority_metrics) — отдельный state, обрабатываем рано.
    if state in (_STATE_AWAIT_PRIORITIES, _STATE_AWAIT_PRIORITIES_RETRY):
        try:
            raw = validate_user_text((update.effective_message.text or "").strip())
        except InputValidationError as e:
            await update.effective_message.reply_text(str(e))
            return True
        return await _handle_priorities_text(update, context, raw)

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
    word_count = len(raw.split())

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        # Получаем scale, чтобы quality_check адаптировался под размер
        app_for_scale = await session.get(Application, app_uuid)
        scale = (app_for_scale.payload or {}).get("company_scale") if app_for_scale else None
        passed, missing = _quality_check(raw, q, scale=scale)

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
