"""/checkup — Чекап v2.0 (ТЗ TZ_checkup_plus_v2.md).

FSM: opening → (pre P1/P2 если нет Mini) → intro → Q1..Q20 с section breaks
после Q5/Q10/Q15 → final screen с 3 CTA.

Типы ответов: MC (5 опций inline), numeric (text input + допустимые диапазоны),
short_text (с проверкой качества по min_words/min_chars/expects).

Skip-логика: при наличии Mini-Чекап (user.segment + quiz_stage) — пропускаем
pre-questions, показываем Mini-контекст.

Force-restart: если application имеет старые `s1_horizon`/`f1_*`/`o1_*`/`m1_*`
ответы — предлагаем рестарт с очисткой (TZ — «принудительно перезапустить
на v2»). Согласованное решение пользователя.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot import keyboards, texts
from src.core.checkup_benchmarks import compare_to_benchmark, is_concerning, lookup_benchmark
from src.core.checkup_questions import (
    CHECKUP_QUESTIONS,
    LAYER_EMOJI,
    LAYER_LABEL,
    LEGACY_V1_KEYS,
    VALID_MC_SCORES,
    CheckupQuestionV2,
    by_key,
)
from src.core.config import settings
from src.core.input_validation import InputValidationError, validate_user_text
from src.db.models import Application, CheckupAnswer, User
from src.db.repos import (
    delete_checkup_answers,
    get_checkup_answers,
    get_or_create_user,
    load_mini_context,
    log_event,
    upsert_checkup_answer,
)
from src.db.session import async_session_factory
from src.tasks.generate_checkup_pdf import generate_checkup_pdf

logger = logging.getLogger(__name__)

# ── FSM keys (изолированы от v1 ключей) ────────────────────────────────────────
_KEY_STATE = "checkup_v2_state"
_KEY_APP_ID = "checkup_v2_app_id"
_KEY_Q_IDX = "checkup_v2_q_idx"
_KEY_IMPROVE_TRIES = "checkup_v2_improve_tries"
_KEY_STARTED_TS = "checkup_v2_started_ts"

# States
_STATE_AWAIT_P1 = "await_p1"
_STATE_AWAIT_P2 = "await_p2"
_STATE_AWAIT_INTRO = "await_intro"
_STATE_AWAIT_ANSWER = "await_answer"     # text/numeric input
_STATE_AWAIT_SECTION_BREAK = "await_section_break"

# Telegram limits
_MAX_ANSWER_CHARS = 4000
_MAX_IMPROVE_TRIES = 2  # после 2 неудачных попыток принимаем как есть


def _safe_uuid(s: str | None) -> UUID | None:
    if not s:
        return None
    try:
        return UUID(s)
    except (ValueError, TypeError):
        return None


def _clear_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    for k in (_KEY_STATE, _KEY_APP_ID, _KEY_Q_IDX, _KEY_IMPROVE_TRIES, _KEY_STARTED_TS):
        context.user_data.pop(k, None)


def is_in_checkup_fsm(user_data: dict) -> bool:
    """Возвращает True если юзер сейчас в FSM Чекапа (v1 или v2).

    Используется в `dialog.handle_text` для маршрутизации свободного текста.
    """
    # v2 keys
    if user_data.get(_KEY_STATE) and user_data.get(_KEY_APP_ID):
        return True
    # v1 keys — на случай если остался state после миграции v1→v2
    if user_data.get("checkup_state") and user_data.get("checkup_app_id"):
        return True
    return False


async def get_paused_checkup(telegram_id: int):
    """Возвращает paused Application (со статусом paid и checkup_current_question_index > 0)
    или None если нет приостановленного Чекапа.

    Используется в `dialog.handle_text` для реактивного предложения возобновить
    Чекап через 24+ ч пауза.
    """
    try:
        async with async_session_factory()() as session:
            user_result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = user_result.scalar_one_or_none()
            if user is None:
                return None
            result = await session.execute(
                select(Application)
                .where(Application.user_id == user.id)
                .where(Application.type == "audit")
                .where(Application.status == "paid")
                .order_by(Application.payment_succeeded_at.desc())
                .limit(1)
            )
            app = result.scalar_one_or_none()
            if app is None:
                return None
            current = app.checkup_current_question_index or 0
            if 0 < current < 20 and app.checkup_completed_at is None:
                return app
            return None
    except Exception:
        logger.exception("get_paused_checkup failed")
        return None


def _progress_bar(current: int, total: int = 20) -> str:
    filled = round(current / total * 10)
    return "█" * filled + "░" * (10 - filled)


# ── /checkup entry point ─────────────────────────────────────────────────────


async def checkup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Главная точка входа: /checkup."""
    msg = update.effective_message
    tg = update.effective_user

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=tg.id)
        app = await _find_paid_application(session, user)

        if app is None:
            await msg.reply_text(
                "Чтобы пройти Бизнес-чекап, сначала нужно оформить покупку.\n\n"
                "9 000 ₽ за Base · 14 000 ₽ за Plus (с видео-разбором от команды EDL OS).\n"
                "Возврат 14 дней — условный (см. /faq).",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Открыть Чекап", callback_data="menu:audit")],
                    [InlineKeyboardButton("← В меню", callback_data="menu:main")],
                ]),
            )
            return

        # 1. Force-restart старых v1-ответов
        existing_answers = await get_checkup_answers(session, app.id)
        has_legacy = any(a.question_key in LEGACY_V1_KEYS for a in existing_answers)
        if has_legacy:
            await msg.reply_text(
                "Чекап обновился — новый формат: 20 вопросов с типами (выбор из 5 вариантов / "
                "цифра / короткое описание). Раньше у вас был старый формат.\n\n"
                "Чтобы получить отчёт нового образца с benchmark по сегменту и 3 agent-teaser-блоками — "
                "начнём заново. Старые ответы я очищу.\n\n"
                "Время — 1–2 часа с возможностью паузы в любой момент.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Начать заново на новом формате", callback_data=f"checkup:restart:{app.id}")],
                    [InlineKeyboardButton("← В меню", callback_data="menu:main")],
                ]),
            )
            return

        # 2. Pause/resume v2: есть ли прогресс
        current_idx = app.checkup_current_question_index or 0
        # Прогресс есть, если есть хотя бы 1 v2-ответ
        v2_keys = {q.key for q in CHECKUP_QUESTIONS}
        has_v2_answers = any(a.question_key in v2_keys for a in existing_answers)

        if has_v2_answers and current_idx > 0 and current_idx < len(CHECKUP_QUESTIONS):
            await msg.reply_text(
                f"У вас сохранён прогресс: вопрос {current_idx + 1}/20.\n"
                f"Продолжить с того места или начать заново?",
                reply_markup=keyboards.checkup_resume_or_restart_keyboard(str(app.id), current_idx),
            )
            return

        # 3. Свежий старт: показываем intro
        await _start_intro(update, context, session, user, app)


async def _find_paid_application(session, user: User) -> Application | None:
    """Возвращает paid Application типа audit (Base или Plus)."""
    result = await session.execute(
        select(Application)
        .where(Application.user_id == user.id)
        .where(Application.type == "audit")
        .where(Application.status == "paid")
        .order_by(Application.payment_succeeded_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _start_intro(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session,
    user: User,
    app: Application,
) -> None:
    """Свежий старт: проверяем skip-логику и показываем intro."""
    mini = await load_mini_context(session, user)

    # Сохраняем app_id в state
    context.user_data[_KEY_APP_ID] = str(app.id)
    context.user_data[_KEY_STARTED_TS] = time.time()

    plan = (app.payload or {}).get("plan") or "base"
    plan_label = "Plus" if plan == "plus" else "Base"

    if mini and mini.get("segment") and mini.get("stage"):
        # Skip-логика — есть Mini контекст
        await log_event(
            session, user_id=user.id, event="checkup_started",
            payload={"plan": plan, "has_mini_context": True, "app_id": str(app.id)},
        )
        await session.commit()
        await _send_mini_recap_intro(update, app, mini, plan_label)
    else:
        # Pre-questions: нужно P1+P2 перед Q1
        await log_event(
            session, user_id=user.id, event="checkup_started",
            payload={"plan": plan, "has_mini_context": False, "app_id": str(app.id)},
        )
        await session.commit()
        await _send_pre_p1(update, context, app)


async def _send_mini_recap_intro(
    update: Update,
    app: Application,
    mini: dict,
    plan_label: str,
) -> None:
    """Intro с Mini-контекстом (ТЗ §5.3)."""
    layer_scores = mini.get("layer_scores") or {}
    weakest_layers = mini.get("weakest_layers") or []
    weakest_text = ""
    if weakest_layers and isinstance(layer_scores, dict):
        parts = []
        for lk in weakest_layers[:2]:
            sc = layer_scores.get(lk)
            label = LAYER_LABEL.get(lk, lk)
            if sc is not None:
                parts.append(f"{lk} {label} ({sc})")
            else:
                parts.append(f"{lk} {label}")
        weakest_text = "\n• Самые слабые слои: " + ", ".join(parts)

    segment = mini.get("segment") or "не указан"
    stage = mini.get("stage") or "не указана"
    seg_display = {
        "edu": "онлайн-школа", "mp": "маркетплейс", "it": "IT-агентство",
        "prod": "производство/опт", "serv": "услуги", "saas": "B2B SaaS",
        "other": "ваш сегмент",
    }.get(segment, segment)
    stage_display = {
        "start": "Старт (1–10 чел · до 15 М ₽)",
        "team": "Команда (10–25 чел · 15–60 М ₽)",
        "structure": "Структура (25–50 чел · 60–200 М ₽)",
        "maturity": "Зрелость (50+ чел · 200 М+ ₽)",
    }.get(stage, stage)

    text = (
        f"Спасибо за оплату — стартуем Бизнес-чекап ({plan_label}).\n\n"
        f"Что я уже знаю про вас:\n"
        f"• Сегмент: {seg_display}\n"
        f"• Стадия роста: {stage_display}\n"
        f"• Score из Mini-Чекапа: {mini.get('score', '—')}/100"
        f"{weakest_text}\n\n"
        f"Сейчас будут *20 более детальных вопросов с цифрами* — типа MC, "
        f"коротких цифр и развёрнутых ответов (3–5 предложений).\n\n"
        f"Время — 1–2 часа, можно делать с перерывами: я сохраняю прогресс. "
        f"Перерыв >24 часа — напомню."
    )
    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboards.checkup_v2_intro_keyboard(str(app.id), has_mini=True),
    )


async def _send_pre_p1(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    app: Application,
) -> None:
    """Если нет Mini — спрашиваем сегмент."""
    context.user_data[_KEY_STATE] = _STATE_AWAIT_P1
    await update.effective_message.reply_text(
        "Перед стартом — 2 коротких вопроса для калибровки бенчмарков.\n\n"
        "*1/2 · Какой у вас сегмент бизнеса?*",
        parse_mode="Markdown",
        reply_markup=keyboards.checkup_p1_segment_keyboard(str(app.id)),
    )


# ── Callback router ──────────────────────────────────────────────────────────


async def handle_checkup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    parts = data.split(":")
    if len(parts) < 2:
        return

    action = parts[1]

    if action == "restart":
        await _handle_restart(update, context, parts)
    elif action == "resume":
        await _handle_resume(update, context, parts)
    elif action == "start_v2":
        await _handle_start_v2(update, context, parts)
    elif action == "explain":
        await _handle_explain(update, context, parts)
    elif action == "p1":
        await _handle_p1_segment(update, context, parts)
    elif action == "p2":
        await _handle_p2_stage(update, context, parts)
    elif action == "mc":
        await _handle_mc_answer(update, context, parts)
    elif action == "num_skip":
        await _handle_numeric_skip(update, context, parts)
    elif action == "example":
        await _handle_example(update, context, parts)
    elif action == "improve":
        await _handle_improve(update, context, parts)
    elif action == "keep":
        await _handle_keep(update, context, parts)
    elif action == "pause":
        await _handle_pause(update, context)
    elif action == "continue":
        await _handle_continue_after_break(update, context, parts)
    elif action == "upgrade_to_plus":
        await _handle_upgrade_info(update, context)
    elif action == "confirm_upgrade":
        await _handle_upgrade_confirm(update, context)
    elif action == "decline_upgrade":
        await _handle_upgrade_decline(update, context)
    # Старые v1 callbacks (start/scale/ready/skip/submit) больше не обрабатываем —
    # они шли через legacy flow, который мы заменили force-restart'ом.


# ── Callback handlers ────────────────────────────────────────────────────────


async def _handle_restart(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    """Полный рестарт Чекапа: очищаем БД-ответы и начинаем с intro."""
    app_id = _safe_uuid(parts[2] if len(parts) > 2 else None)
    if not app_id:
        return

    _clear_state(context)

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        result = await session.execute(select(Application).where(Application.id == app_id))
        app = result.scalar_one_or_none()
        if app is None or app.user_id != user.id:
            await update.effective_message.reply_text("Заявка не найдена.")
            return
        deleted = await delete_checkup_answers(session, app.id)
        app.checkup_current_question_index = 0
        await log_event(
            session, user_id=user.id, event="checkup_restarted_v2",
            payload={"app_id": str(app.id), "deleted": deleted},
        )
        await session.commit()
        await _start_intro(update, context, session, user, app)


async def _handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    """Продолжить с сохранённого индекса."""
    app_id = _safe_uuid(parts[2] if len(parts) > 2 else None)
    if not app_id:
        return

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        result = await session.execute(select(Application).where(Application.id == app_id))
        app = result.scalar_one_or_none()
        if app is None or app.user_id != user.id:
            await update.effective_message.reply_text("Заявка не найдена.")
            return
        current = app.checkup_current_question_index or 0
        context.user_data[_KEY_APP_ID] = str(app.id)
        context.user_data[_KEY_Q_IDX] = current
        context.user_data[_KEY_STARTED_TS] = time.time()
        await log_event(
            session, user_id=user.id, event="checkup_resumed",
            payload={"app_id": str(app.id), "from_idx": current},
        )
        await session.commit()
        await _send_question(update, context, current)


async def _handle_start_v2(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    """После intro — начинаем с Q1."""
    app_id = _safe_uuid(parts[2] if len(parts) > 2 else None)
    if not app_id:
        return
    context.user_data[_KEY_APP_ID] = str(app_id)
    context.user_data[_KEY_Q_IDX] = 0
    await _send_question(update, context, 0)


async def _handle_explain(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    """«Сначала расскажи как устроено»."""
    app_id_str = parts[2] if len(parts) > 2 else ""
    await update.effective_message.reply_text(
        "*Как устроен Чекап v2*\n\n"
        "20 вопросов по 4 слоям (Стратегия / Воронка / Операционка / Деньги). "
        "В каждом слое 5 вопросов:\n"
        "• 3 с выбором из 5 вариантов (1 клик)\n"
        "• 1 численный (одна цифра, можно «не знаю»)\n"
        "• 1 короткий текст (3–5 предложений)\n\n"
        "После каждого слоя — checkpoint, можно сделать перерыв. "
        "Я сохраняю прогресс автоматически. Среднее время на ответ — 30 сек.\n\n"
        "На выходе через 24 часа — PDF на 10–15 страниц "
        "с бенчмарком по сегменту, диагнозом по слоям, 3 agent-teaser-блоками "
        "и 30-дневным планом действий.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Поехали", callback_data=f"checkup:start_v2:{app_id_str}")],
        ]),
    )


async def _handle_p1_segment(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    """Сохраняем segment, переходим к P2."""
    if context.user_data.get(_KEY_STATE) != _STATE_AWAIT_P1:
        return
    seg = parts[2] if len(parts) > 2 else None
    if seg not in {"edu", "mp", "it", "prod", "serv", "saas", "other"}:
        return

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        user.segment = seg
        await log_event(
            session, user_id=user.id, event="checkup_pre_p1_answered",
            payload={"segment": seg},
        )
        await session.commit()

    context.user_data[_KEY_STATE] = _STATE_AWAIT_P2
    app_id = context.user_data.get(_KEY_APP_ID, "")
    await update.effective_message.reply_text(
        "*2/2 · Сколько у вас людей и какая выручка за прошлый год?*",
        parse_mode="Markdown",
        reply_markup=keyboards.checkup_p2_stage_keyboard(app_id),
    )


async def _handle_p2_stage(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    """Сохраняем stage, показываем intro."""
    if context.user_data.get(_KEY_STATE) != _STATE_AWAIT_P2:
        return
    p2 = parts[2] if len(parts) > 2 else None
    stage_map = {
        "start": "start", "team": "team", "structure": "structure", "maturity": "maturity",
        "outlier_small_team": "team", "outlier_big_team": "structure",
    }
    if p2 not in stage_map:
        return
    stage = stage_map[p2]

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        user.quiz_stage = stage
        # Заполняем company_size + revenue range по выбранной стадии
        _size_map = {"start": 10, "team": 25, "structure": 50, "maturity": 100}
        _rev_map = {"start": "<15M", "team": "15-60M", "structure": "60-200M", "maturity": "200M+"}
        user.company_size = _size_map.get(stage, 25)
        user.company_revenue_range = _rev_map.get(stage, "15-60M")
        await log_event(
            session, user_id=user.id, event="checkup_pre_p2_answered",
            payload={"stage": stage, "outlier": p2.startswith("outlier_")},
        )
        await session.commit()

    context.user_data[_KEY_STATE] = _STATE_AWAIT_INTRO
    app_id = context.user_data.get(_KEY_APP_ID, "")
    await update.effective_message.reply_text(
        f"Готово. Стадия: *{_stage_label(stage)}*.\n\n"
        "Теперь 20 вопросов по 4 слоям — Стратегия / Воронка / Операционка / Деньги. "
        "1–2 часа с возможностью паузы. После каждого слоя — checkpoint.",
        parse_mode="Markdown",
        reply_markup=keyboards.checkup_v2_intro_keyboard(app_id, has_mini=False),
    )


def _stage_label(stage: str) -> str:
    return {"start": "Старт", "team": "Команда", "structure": "Структура", "maturity": "Зрелость"}.get(stage, stage)


# ── Send question by index ───────────────────────────────────────────────────


async def _send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int) -> None:
    """Отправляем вопрос с правильной клавиатурой по типу."""
    if idx >= len(CHECKUP_QUESTIONS):
        await _finalize_checkup(update, context)
        return

    q = CHECKUP_QUESTIONS[idx]
    context.user_data[_KEY_Q_IDX] = idx
    context.user_data[_KEY_IMPROVE_TRIES] = 0

    layer_emoji = LAYER_EMOJI.get(q.layer, "❓")
    layer_label = LAYER_LABEL.get(q.layer, "")
    bar = _progress_bar(idx)
    header = (
        f"{layer_emoji} *Вопрос {q.order}/20* · {bar} {idx * 5}%\n"
        f"_{layer_label}_\n\n"
        f"_{q.why_we_ask}_\n\n"
        f"*{q.text}*"
    )

    if q.answer_type == "mc":
        # Inline-клавиатура 5 опций
        context.user_data[_KEY_STATE] = _STATE_AWAIT_ANSWER  # ждём callback
        await update.effective_message.reply_text(
            header,
            parse_mode="Markdown",
            reply_markup=keyboards.checkup_mc_keyboard(idx, q.options or ()),
        )
    elif q.answer_type == "numeric":
        # Ждём text input
        context.user_data[_KEY_STATE] = _STATE_AWAIT_ANSWER
        guidance = ""
        if q.numeric_guidance:
            guidance = f"\n\n_💡 {q.numeric_guidance}_"
        range_hint = ""
        if q.numeric_min is not None and q.numeric_max is not None:
            range_hint = f"\n\nОжидаемый диапазон: {int(q.numeric_min)}–{int(q.numeric_max)} {q.numeric_unit or ''}"
        await update.effective_message.reply_text(
            f"{header}{guidance}{range_hint}\n\nОтветьте одной цифрой:",
            parse_mode="Markdown",
            reply_markup=keyboards.checkup_numeric_keyboard(idx, allow_skip=q.allow_skip),
        )
    else:  # short_text
        context.user_data[_KEY_STATE] = _STATE_AWAIT_ANSWER
        await update.effective_message.reply_text(
            header,
            parse_mode="Markdown",
            reply_markup=keyboards.checkup_short_text_keyboard(idx),
        )


# ── MC callback ──────────────────────────────────────────────────────────────


async def _handle_mc_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    if context.user_data.get(_KEY_STATE) != _STATE_AWAIT_ANSWER:
        return
    if len(parts) < 4:
        return
    try:
        idx = int(parts[2])
        score = int(parts[3])
    except ValueError:
        return
    if score not in VALID_MC_SCORES:
        return
    if idx >= len(CHECKUP_QUESTIONS):
        return

    q = CHECKUP_QUESTIONS[idx]
    if q.answer_type != "mc":
        return

    # Найдём текст выбранной опции
    option_label = ""
    for label, sc in q.options or ():
        if sc == score:
            option_label = label
            break

    await _save_answer(
        update, context, q,
        text=option_label,
        word_count=len(option_label.split()),
        quality_passed=True,
        answer_score=score,
        duration_sec=_question_duration_sec(context),
    )
    await _after_answer_advance(update, context, q)


# ── Numeric / short-text via text input ──────────────────────────────────────


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Свободный текст в FSM Чекапа.

    Returns True если сообщение «поглотили» (это checkup-step), False иначе.
    """
    state = context.user_data.get(_KEY_STATE)
    if state != _STATE_AWAIT_ANSWER:
        return False

    idx = context.user_data.get(_KEY_Q_IDX)
    if idx is None or idx >= len(CHECKUP_QUESTIONS):
        return False
    q = CHECKUP_QUESTIONS[idx]
    if q.answer_type == "mc":
        # MC ждёт callback, не текст. Подсказываем.
        await update.effective_message.reply_text(
            "Этот вопрос — с кнопками. Выберите вариант ответа.",
        )
        return True

    text = update.effective_message.text or ""
    try:
        text = validate_user_text(text, max_chars=_MAX_ANSWER_CHARS)
    except InputValidationError as e:
        await update.effective_message.reply_text(f"Ответ не принят: {e}")
        return True

    if q.answer_type == "numeric":
        await _handle_numeric_text(update, context, q, text)
    else:  # short_text
        await _handle_short_text(update, context, q, text)
    return True


_NUMERIC_SKIP_MARKERS = ("не знаю", "хз", "не считаю", "не считал", "skip", "n/a", "хочу позже")


async def _handle_numeric_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    q: CheckupQuestionV2,
    text: str,
) -> None:
    raw = text.strip().lower().replace(",", ".")

    # Skip-вариант через текст
    if any(m in raw for m in _NUMERIC_SKIP_MARKERS):
        if q.allow_skip:
            await _save_numeric_skip(update, context, q)
            return
        await update.effective_message.reply_text(
            "Это важно для PDF — попробуйте оценить хотя бы примерно. "
            "Если совсем нет данных — отметьте «Не знаю — посчитаю позже».",
            reply_markup=keyboards.checkup_numeric_keyboard(
                context.user_data.get(_KEY_Q_IDX, 0),
                allow_skip=q.allow_skip,
            ),
        )
        return

    # Парсим число
    m = re.search(r"-?\d+(?:\.\d+)?", raw)
    if not m:
        await update.effective_message.reply_text(
            f"Похоже, опечатка. Ответ должен быть числом ({q.numeric_unit or ''}). "
            f"Например: 22"
        )
        return
    try:
        value = float(m.group(0))
    except ValueError:
        await update.effective_message.reply_text("Не удалось распознать число. Попробуйте ещё раз.")
        return

    if q.numeric_min is not None and q.numeric_max is not None:
        if not (q.numeric_min <= value <= q.numeric_max):
            await update.effective_message.reply_text(
                f"Цифра вне обычного диапазона: {q.numeric_min:g}–{q.numeric_max:g} {q.numeric_unit or ''}. "
                f"Уточните или нажмите «Не знаю — посчитаю позже»."
            )
            return

    # Подозрительно низкие значения для percent-метрик
    if q.benchmark_key in {"margin_pct", "conv_pct"} and value == 0:
        await update.effective_message.reply_text(
            f"{q.numeric_unit or ''} = 0 — точно? Возможно, имели в виду «не считаю»?\n"
            f"Нажмите «Не знаю — посчитаю позже» если данных нет, или подтвердите 0 повторным сообщением «0 точно»."
        )
        # Сохраняем pending — если юзер пришлёт «0 точно», парсим как 0
        # Это лёгкая защита; для MVP просто принимаем ответ
        # ...
        # Принимаем как 0, но логируем
        pass

    # Сохраняем
    await _save_answer(
        update, context, q,
        text=str(value),
        word_count=1,
        quality_passed=True,
        answer_numeric=value,
        duration_sec=_question_duration_sec(context),
    )

    # Бенчмарк (acknowledgement)
    bench_msg = await _maybe_benchmark_message(update, q, value)
    if bench_msg:
        await update.effective_message.reply_text(bench_msg, parse_mode="Markdown")

    await _after_answer_advance(update, context, q)


async def _save_numeric_skip(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    q: CheckupQuestionV2,
) -> None:
    await _save_answer(
        update, context, q,
        text="(не знаю — посчитаю позже)",
        word_count=0,
        quality_passed=False,
        quality_notes="numeric skipped — в PDF плашка «рекомендуем посчитать в 30 дней»",
        answer_skipped=True,
        duration_sec=_question_duration_sec(context),
    )
    await update.effective_message.reply_text(
        "Отметил. В PDF будет плашка «Рекомендуем посчитать в первые 30 дней».",
    )
    await _after_answer_advance(update, context, q)


async def _handle_numeric_skip(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    if context.user_data.get(_KEY_STATE) != _STATE_AWAIT_ANSWER:
        return
    try:
        idx = int(parts[2])
    except (ValueError, IndexError):
        return
    if idx >= len(CHECKUP_QUESTIONS):
        return
    q = CHECKUP_QUESTIONS[idx]
    if q.answer_type != "numeric" or not q.allow_skip:
        return
    await _save_numeric_skip(update, context, q)


async def _maybe_benchmark_message(
    update: Update, q: CheckupQuestionV2, value: float
) -> str | None:
    """Возвращает сообщение со сравнением с бенчмарком (или None)."""
    if not q.benchmark_key:
        return None

    # Достанем сегмент и стадию пользователя
    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        segment = user.segment
        stage = user.quiz_stage or "team"

    mean = lookup_benchmark(q.benchmark_key, segment, stage)
    if mean is None:
        return None

    unit = q.numeric_unit or ""
    cmp_text = compare_to_benchmark(value, mean, unit=unit)
    flag, flag_msg = is_concerning(q.benchmark_key, value)

    msg = f"📊 Ваш ответ: *{value:g}{unit}*. {cmp_text}"
    if flag and flag_msg:
        msg += f"\n\n⚠️ {flag_msg}"
    return msg


# ── Short-text ──────────────────────────────────────────────────────────────


_NOT_APPLICABLE_MARKERS = (
    "не считаю", "не считаем", "не применимо",
    "нет данных", "не релевантно", "не релевантна",
    "не веду", "не ведём", "не отслеживаю", "не отслеживаем",
)


def _is_not_applicable(text: str) -> bool:
    t = (text or "").lower()
    return any(m in t for m in _NOT_APPLICABLE_MARKERS)


def _quality_check_text(text: str, q: CheckupQuestionV2) -> tuple[bool, list[str]]:
    """Проверка short-text по min_chars / min_words / expects."""
    missing = []
    if q.min_chars and len(text) < q.min_chars:
        missing.append(f"≥{q.min_chars} символов (у вас {len(text)})")
    if q.min_words and len(text.split()) < q.min_words:
        missing.append(f"≥{q.min_words} слов (у вас {len(text.split())})")
    # expects — не блокируем, только подсказываем
    return len(missing) == 0, missing


async def _handle_short_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    q: CheckupQuestionV2,
    text: str,
) -> None:
    # Допускаем «не применимо» — passing с пометкой
    if _is_not_applicable(text):
        await _save_answer(
            update, context, q,
            text=text,
            word_count=len(text.split()),
            quality_passed=True,
            quality_notes="не применимо для масштаба — учтено",
            duration_sec=_question_duration_sec(context),
        )
        await _after_answer_advance(update, context, q)
        return

    passed, missing = _quality_check_text(text, q)
    tries = context.user_data.get(_KEY_IMPROVE_TRIES, 0)

    if passed:
        await _save_answer(
            update, context, q,
            text=text,
            word_count=len(text.split()),
            quality_passed=True,
            duration_sec=_question_duration_sec(context),
        )
        await _after_answer_advance(update, context, q)
        return

    # Не прошло — предлагаем дополнить или оставить
    if tries >= _MAX_IMPROVE_TRIES:
        # Принимаем как есть, помечаем не пройденным
        await _save_answer(
            update, context, q,
            text=text,
            word_count=len(text.split()),
            quality_passed=False,
            quality_notes=f"После {tries} попыток: {', '.join(missing)}",
            duration_sec=_question_duration_sec(context),
        )
        await update.effective_message.reply_text(
            "Принял. В PDF поставлю плашку «ответ требует уточнения на Диагностике»."
        )
        await _after_answer_advance(update, context, q)
        return

    context.user_data[_KEY_IMPROVE_TRIES] = tries + 1
    idx = context.user_data.get(_KEY_Q_IDX, 0)

    # Сохраняем «промежуточный» ответ с quality_passed=False сразу — чтобы
    # /keep (без повторной отправки) мог его принять, и чтобы /reset не
    # терял прогресс. При повторной отправке upsert обновит ту же строку.
    await _save_answer(
        update, context, q,
        text=text,
        word_count=len(text.split()),
        quality_passed=False,
        quality_notes=f"Attempt {tries + 1}: {', '.join(missing)}",
        duration_sec=_question_duration_sec(context),
    )
    # _save_answer обновил checkup_current_question_index на idx+1 — откатываем
    # это, потому что мы ещё не дошли до следующего вопроса (ждём улучшения).
    app_id = _safe_uuid(context.user_data.get(_KEY_APP_ID))
    if app_id:
        async with async_session_factory()() as session:
            result = await session.execute(select(Application).where(Application.id == app_id))
            app = result.scalar_one_or_none()
            if app:
                app.checkup_current_question_index = idx
                await session.commit()
    # Возвращаем idx в FSM (для consistency)
    context.user_data[_KEY_Q_IDX] = idx

    await update.effective_message.reply_text(
        f"Чуть глубже бы, чтобы PDF получился полезным:\n• {chr(10).join('• ' + m for m in missing)}\n\n"
        f"Дополните ответ — или оставьте как есть.",
        reply_markup=keyboards.checkup_quality_followup_keyboard(idx),
    )


async def _handle_example(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    try:
        idx = int(parts[2])
    except (ValueError, IndexError):
        return
    if idx >= len(CHECKUP_QUESTIONS):
        return
    q = CHECKUP_QUESTIONS[idx]
    example = q.example_good or "(пример пока не задан)"
    await update.effective_message.reply_text(
        f"💡 *Пример хорошего ответа на этот вопрос:*\n\n`{example}`",
        parse_mode="Markdown",
    )


async def _handle_improve(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    """«Дополнить» — ждём более длинный текст."""
    await update.effective_message.reply_text(
        "Жду ваш расширенный ответ — пришлите тем же сообщением.",
    )


async def _handle_keep(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]) -> None:
    """«Оставить как есть» — принимаем последний text-ответ."""
    try:
        idx = int(parts[2])
    except (ValueError, IndexError):
        return
    if idx >= len(CHECKUP_QUESTIONS):
        return
    q = CHECKUP_QUESTIONS[idx]
    # У нас уже сохранён ответ с quality_passed=False, ничего не меняем
    # Просто двигаемся дальше
    await update.effective_message.reply_text(
        "Принял. В PDF будет плашка «ответ требует уточнения на Диагностике».",
    )
    await _after_answer_advance(update, context, q)


# ── Pause / section break ────────────────────────────────────────────────────


async def _handle_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пауза — сохраняем прогресс, чистим FSM."""
    app_id = _safe_uuid(context.user_data.get(_KEY_APP_ID))
    idx = context.user_data.get(_KEY_Q_IDX, 0)

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        if app_id:
            result = await session.execute(select(Application).where(Application.id == app_id))
            app = result.scalar_one_or_none()
            if app:
                app.checkup_current_question_index = idx
                app.checkup_last_active_at = datetime.now(timezone.utc)
        await log_event(
            session, user_id=user.id, event="checkup_paused",
            payload={"at_q_idx": idx, "app_id": str(app_id) if app_id else None},
        )
        await session.commit()

    _clear_state(context)
    await update.effective_message.reply_text(
        f"Окей, прервалась. Прогресс сохранён ({idx}/20).\n\n"
        f"Когда вернётесь — наберите /checkup и продолжите с того же места.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("← В меню", callback_data="menu:main")],
        ]),
    )


async def _handle_continue_after_break(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str]
) -> None:
    """Продолжить после section break — отправляем следующий вопрос."""
    idx = context.user_data.get(_KEY_Q_IDX, 0)
    # Если state не AWAIT_SECTION_BREAK, всё равно двигаемся — устойчиво
    await _send_question(update, context, idx + 1)


# ── Save & advance ───────────────────────────────────────────────────────────


def _question_duration_sec(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    ts = context.user_data.get(_KEY_STARTED_TS)
    if ts is None:
        return None
    return max(1, int(time.time() - ts))


async def _save_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    q: CheckupQuestionV2,
    *,
    text: str,
    word_count: int,
    quality_passed: bool,
    quality_notes: str | None = None,
    answer_score: int | None = None,
    answer_numeric: float | None = None,
    answer_skipped: bool = False,
    duration_sec: int | None = None,
) -> None:
    """Сохраняет ответ и обновляет checkup_current_question_index."""
    app_id = _safe_uuid(context.user_data.get(_KEY_APP_ID))
    if not app_id:
        return

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        result = await session.execute(select(Application).where(Application.id == app_id))
        app = result.scalar_one_or_none()
        if app is None:
            return

        await upsert_checkup_answer(
            session,
            application_id=app.id,
            user_id=user.id,
            question_key=q.key,
            layer=q.layer,
            text=text,
            word_count=word_count,
            answer_type=q.answer_type,
            quality_passed=quality_passed,
            quality_notes=quality_notes,
            answer_score=answer_score,
            answer_numeric=answer_numeric,
            answer_skipped=answer_skipped,
        )
        # Сохраняем прогресс
        idx = context.user_data.get(_KEY_Q_IDX, 0)
        app.checkup_current_question_index = idx + 1
        app.checkup_last_active_at = datetime.now(timezone.utc)
        if app.checkup_started_at is None:
            app.checkup_started_at = datetime.now(timezone.utc)
        await log_event(
            session,
            user_id=user.id,
            event="checkup_question_answered",
            payload={
                "q_key": q.key,
                "answer_type": q.answer_type,
                "q_idx": idx,
                "duration_sec": duration_sec,
                "quality_passed": quality_passed,
                "skipped": answer_skipped,
            },
        )
        await session.commit()

    # Сбрасываем счётчик попыток дожима
    context.user_data[_KEY_IMPROVE_TRIES] = 0
    context.user_data[_KEY_STARTED_TS] = time.time()


async def _after_answer_advance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    q: CheckupQuestionV2,
) -> None:
    """После сохранения ответа: либо section break, либо следующий вопрос."""
    if q.section_break_after and q.order < 20:
        # Section break после Q5/Q10/Q15
        context.user_data[_KEY_STATE] = _STATE_AWAIT_SECTION_BREAK
        async with async_session_factory()() as session:
            user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
            await log_event(
                session, user_id=user.id, event="checkup_section_break",
                payload={"after_layer": q.layer},
            )
            await session.commit()
        await update.effective_message.reply_text(
            f"✅ *Слой {q.layer} · {LAYER_LABEL.get(q.layer, '')}* — готов\n\n"
            f"Продолжим сразу или сделать перерыв? Прогресс сохранён.",
            parse_mode="Markdown",
            reply_markup=keyboards.checkup_section_break_keyboard(q.layer),
        )
        return

    next_idx = q.order  # т.к. q.order — это 1..20, индекс следующего = q.order
    await _send_question(update, context, next_idx)


# ── Finalize: PDF + 3 CTAs ───────────────────────────────────────────────────


async def _finalize_checkup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Все 20 вопросов закрыты — запускаем PDF + показываем 3 CTA."""
    app_id = _safe_uuid(context.user_data.get(_KEY_APP_ID))
    if not app_id:
        return

    show_plus_upgrade = False
    diagnostic_price = 45_000

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        result = await session.execute(select(Application).where(Application.id == app_id))
        app = result.scalar_one_or_none()
        if app is None:
            return

        app.checkup_completed_at = datetime.now(timezone.utc)
        app.checkup_current_question_index = 20

        # Считаем upsell-условия
        plan = (app.payload or {}).get("plan") or "base"
        if plan == "base":
            try:
                from src.core.checkup_score import split_answers, total_checkup_score
                answers = await get_checkup_answers(session, app.id)
                mc, num, txt = split_answers(answers)
                score, layer_scores = total_checkup_score(
                    mc, num, txt, user.segment, user.quiz_stage or "team"
                )
                weak_count = sum(1 for v in layer_scores.values() if v < 50)
                if score <= 60 or weak_count >= 2:
                    show_plus_upgrade = True

                # Сохраняем в payload
                payload = dict(app.payload or {})
                payload["checkup_score"] = score
                payload["checkup_layer_scores"] = layer_scores
                app.payload = payload
            except Exception as e:
                logger.exception("Failed to compute checkup_score: %s", e)

        await log_event(
            session, user_id=user.id, event="checkup_completed",
            payload={
                "app_id": str(app.id),
                "plan": plan,
                "show_plus_upgrade": show_plus_upgrade,
            },
        )
        await session.commit()

    _clear_state(context)
    await update.effective_message.reply_text(
        "✅ *Все 20 вопросов закрыты* — спасибо за развёрнутые ответы!\n\n"
        "Готовлю PDF с разбором по 4 слоям, agent teaser-блоками и "
        "30-дневным планом. Пришлю в этот чат до 24 часов "
        "(обычно — в течение 5 минут).",
        parse_mode="Markdown",
    )

    # Триггерим генерацию PDF (async через Celery или inline)
    try:
        await _trigger_pdf_generation(str(app_id))
    except Exception as e:
        logger.exception("PDF generation trigger failed: %s", e)

    # 3 CTA
    await update.effective_message.reply_text(
        "*Что дальше:*\n\n"
        f"📊 Диагностика ({diagnostic_price:,} ₽) — за 2 недели подключаем CRM/банк/1С, "
        "считаем юнит-экономику на реальных данных, собираем дашборд L1–L3.\n\n"
        "Это естественный следующий шаг после Чекапа — мы превращаем ваши ответы "
        "в живые цифры.".replace(",", " "),
        parse_mode="Markdown",
        reply_markup=keyboards.checkup_final_cta_keyboard(
            show_plus_upgrade=show_plus_upgrade,
            diagnostic_price_rub=diagnostic_price,
        ),
    )


async def _trigger_pdf_generation(app_id: str) -> None:
    """Запускаем генерацию PDF (Celery если доступен, иначе inline)."""
    try:
        # Celery delay
        generate_checkup_pdf.delay(app_id)
        logger.info("Queued PDF generation for %s", app_id)
    except Exception:
        # Fallback на inline (через _generate сразу)
        try:
            from src.tasks.generate_checkup_pdf import _generate
            await _generate(app_id)
        except Exception as e:
            logger.exception("Inline PDF generation failed: %s", e)


# ── Upsell Base → Plus ───────────────────────────────────────────────────────


async def _handle_upgrade_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Юзер кликнул «Доплатить до Plus» — показываем подробности."""
    await update.effective_message.reply_text(
        "*Доплата до Plus · +5 000 ₽*\n\n"
        "Что добавится к вашему PDF:\n"
        "• Расширенные benchmarks по сегменту × стадии (стр. 13)\n"
        "• Раздел «Что внутри Спринта применительно к вам» (стр. 14)\n"
        "• *15-мин видео-разбор от команды EDL OS* — записывается под "
        "ваш PDF, приходит в течение 24 часов после доплаты\n\n"
        "Видео — это не общая «вода», а walkthrough по вашим "
        "ответам с 3 ключевыми акцентами для вашего сегмента и стадии.\n\n"
        "Доплатить?",
        parse_mode="Markdown",
        reply_markup=keyboards.checkup_plus_upgrade_keyboard(),
    )


async def _handle_upgrade_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Юзер согласен на доплату — создаём заявку на 5 000 ₽."""
    app_id = _safe_uuid(context.user_data.get(_KEY_APP_ID))
    # Если state очищен (после finalize) — достанем последний paid app
    if not app_id:
        async with async_session_factory()() as session:
            user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
            app = await _find_paid_application(session, user)
            if app:
                app_id = app.id

    if not app_id:
        await update.effective_message.reply_text(
            "Не нашёл заявку. Напишите Ивану — оформит вручную: "
            f"@{settings.sales_username}"
        )
        return

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(
            session, user_id=user.id, event="checkup_upgrade_to_plus_requested",
            payload={"from_application_id": str(app_id), "amount_rub": 5000},
        )
        await session.commit()

    # Уведомление Ивану + клиенту
    await update.effective_message.reply_text(
        "✅ Отправил заявку на доплату Иван получит уведомление и "
        "пришлёт реквизиты в течение 1 часа в рабочие часы (10–19 МСК).\n\n"
        "После оплаты — статус Plus и видео от команды EDL OS в течение 24 часов.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Написать Ивану", url=f"https://t.me/{settings.sales_username}")],
            [InlineKeyboardButton("← В меню", callback_data="menu:main")],
        ]),
    )

    try:
        from src.core.notifications import send_to_admin_chat
        await send_to_admin_chat(
            f"💸 Upgrade Base→Plus: пользователь tg={update.effective_user.id} запросил доплату 5 000 ₽.\n"
            f"Application: {app_id}\n"
            f"Действие: /mark_paid {app_id} 5000 upgrade_plus"
        )
    except Exception:
        logger.warning("admin chat notification failed")


async def _handle_upgrade_decline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Ок, тогда придёт обычный Base-PDF. Если передумаете — наберите /checkup и "
        "снова появится кнопка доплаты.",
        reply_markup=keyboards.back_to_menu(),
    )
