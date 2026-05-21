"""Mini-Чекап v2.0 — бот /quiz.

FSM: P1 (сегмент) → P2 (команда+выручка) → Q1..Q12 → result (3 сообщения).
Пропуск P1/P2, если данные уже есть у пользователя.
"""
from __future__ import annotations

import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot import keyboards
from src.core.quiz import (
    LAYER_LABEL,
    QUIZ_QUESTIONS,
    SEGMENT_DISPLAY,
    SEGMENT_LABEL,
    STAGE_DESC,
    STAGE_LABEL,
    build_result,
    category_label,
    layer_color,
    layer_score_0_100,
    stage_detection,
    total_score,
)
from src.db.repos import get_or_create_user, log_event, mark_quiz_completed
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

# ── FSM keys ──────────────────────────────────────────────────────────────────
_KEY_PHASE = "qv2_phase"    # 'p1' | 'p2' | 'q<N>' | 'done'
_KEY_IDX = "qv2_idx"       # 0..11 (index в QUIZ_QUESTIONS)
_KEY_ANS = "qv2_answers"   # {q_key: score}
_KEY_SEG = "qv2_segment"
_KEY_P2 = "qv2_p2_opt"
_KEY_STAGE = "qv2_stage"
_KEY_CONF = "qv2_conf"
_KEY_START = "qv2_start_ts"

# P2 options: callback value → (label, stage_key)
_P2_OPTIONS = [
    ("start",              "1–10 чел · до 15 М ₽"),
    ("team",               "10–25 чел · 15–60 М ₽"),
    ("structure",          "25–50 чел · 60–200 М ₽"),
    ("maturity",           "50+ чел · 200 М+ ₽"),
    ("outlier_small_team", "Команда меньше, чем выручка подсказывает"),
    ("outlier_big_team",   "Команда больше, чем выручка подсказывает"),
]


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запускает Mini-Чекап. Точки входа: /quiz, /score, /start quiz."""
    msg = update.effective_message
    user_tg = update.effective_user

    # Сбрасываем предыдущее состояние
    for k in (_KEY_PHASE, _KEY_IDX, _KEY_ANS, _KEY_SEG, _KEY_P2, _KEY_STAGE, _KEY_CONF, _KEY_START):
        context.user_data.pop(k, None)

    context.user_data[_KEY_START] = time.time()

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=user_tg.id)
        await log_event(session, user_id=user.id, event="quiz_started",
                        payload={"source": "bot", "skip_p1": bool(user.segment),
                                 "skip_p2": bool(user.company_size)})
        await session.commit()

        # Skip-логика: если оба поля заполнены — пропускаем P1/P2
        if user.segment and user.company_size:
            context.user_data[_KEY_SEG] = user.segment
            # company_size сохраняется, определяем стадию из company_revenue_range
            stage, conf = _stage_from_user(user)
            context.user_data[_KEY_STAGE] = stage
            context.user_data[_KEY_CONF] = conf
            context.user_data[_KEY_IDX] = 0
            context.user_data[_KEY_PHASE] = "q0"
            await msg.reply_text(
                "🎯 *Founder OS Score — Mini-Чекап*\n\n"
                "12 вопросов по 4 слоям. Узнаете Score 0–100, сравнение с вашим сегментом "
                "и 3 точки роста.\n\n"
                f"Сегмент и стадия уже сохранены — сразу к вопросам.",
                parse_mode="Markdown",
            )
            await _send_question(update, context, index=0)
        elif user.segment:
            # Есть только сегмент — пропускаем P1, спрашиваем P2
            context.user_data[_KEY_SEG] = user.segment
            context.user_data[_KEY_PHASE] = "p2"
            await _send_intro(update, context, skip_p1=True)
            await _send_p2(update, context)
        else:
            context.user_data[_KEY_PHASE] = "p1"
            await _send_intro(update, context, skip_p1=False)
            await _send_p1(update, context)


def _stage_from_user(user):
    """Определяем стадию из полей users.company_size и company_revenue_range."""
    from src.core.quiz import Stage
    rev = user.company_revenue_range or ""
    size = user.company_size or 0
    if size <= 10 or rev == "<15M":
        return "start", "high"
    if size <= 25 or rev == "15-60M":
        return "team", "high"
    if size <= 50 or rev == "60-200M":
        return "structure", "high"
    return "maturity", "high"


async def _send_intro(update: Update, context: ContextTypes.DEFAULT_TYPE, *, skip_p1: bool) -> None:
    await update.effective_message.reply_text(
        "🎯 *Founder OS Score — Mini-Чекап*\n\n"
        "12 вопросов по 4 слоям. Узнаете Score 0–100, сравнение с вашим сегментом "
        "и 3 точки роста.\n\n"
        "Поехали — 2 быстрых вопроса для настройки Score под ваш бизнес.",
        parse_mode="Markdown",
    )


async def _send_p1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    segs = [
        ("edu",   "Онлайн-школа / EdTech"),
        ("mp",    "Маркетплейс / e-commerce"),
        ("it",    "IT / digital-агентство / разработка"),
        ("prod",  "Производство / опт / B2B-поставки"),
        ("serv",  "Услуги (консалтинг, юр-, бух-, медицина)"),
        ("saas",  "B2B SaaS / подписочный продукт"),
        ("other", "Другое"),
    ]
    buttons = [[InlineKeyboardButton(label, callback_data=f"quiz:p1:{code}")] for code, label in segs]
    markup = InlineKeyboardMarkup(buttons)
    await update.effective_message.reply_text(
        "P1 · Какой у вас сегмент бизнеса?",
        reply_markup=markup,
    )


async def _send_p2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"quiz:p2:{code}")]
        for code, label in _P2_OPTIONS
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.effective_message.reply_text(
        "P2 · Сколько у вас людей и какая выручка за прошлый год?\n\n"
        "Выберите ближайшее сочетание:",
        reply_markup=markup,
    )


async def _send_question(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, index: int
) -> None:
    q = QUIZ_QUESTIONS[index]
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"quiz:ans:{index}:{score}")]
        for label, score in q.options
    ]
    buttons.append([InlineKeyboardButton("✕ Прервать", callback_data="quiz:cancel")])
    markup = InlineKeyboardMarkup(buttons)
    await update.effective_message.reply_text(q.text, reply_markup=markup)


async def handle_p1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback quiz:p1:<segment>."""
    query = update.callback_query
    await query.answer()

    seg = (query.data or "").split(":")[-1]
    if seg not in SEGMENT_DISPLAY and seg != "other":
        return

    context.user_data[_KEY_SEG] = seg
    context.user_data[_KEY_PHASE] = "p2"

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        user.segment = seg
        await log_event(session, user_id=user.id, event="quiz_p1_answered", payload={"segment": seg})
        await session.commit()

    await _send_p2(update, context)


async def handle_p2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback quiz:p2:<option>."""
    query = update.callback_query
    await query.answer()

    opt = (query.data or "").split(":")[-1]
    valid_opts = {code for code, _ in _P2_OPTIONS}
    if opt not in valid_opts:
        return

    stage, conf = stage_detection(opt)
    context.user_data[_KEY_P2] = opt
    context.user_data[_KEY_STAGE] = stage
    context.user_data[_KEY_CONF] = conf
    context.user_data[_KEY_IDX] = 0
    context.user_data[_KEY_PHASE] = "q0"

    is_outlier = opt.startswith("outlier_")
    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        # Сохраняем размер компании (верхняя граница диапазона) и стадию
        _size_map = {"start": 10, "team": 25, "structure": 50, "maturity": 100}
        user.company_size = _size_map.get(stage, 25)
        _rev_map = {"start": "<15M", "team": "15-60M", "structure": "60-200M", "maturity": "200M+"}
        user.company_revenue_range = _rev_map.get(stage, "15-60M")
        await log_event(session, user_id=user.id, event="quiz_p2_answered",
                        payload={"stage": stage, "outlier": is_outlier, "confidence": conf})
        await session.commit()

    if is_outlier and conf == "low":
        await query.message.reply_text(
            f"Понял. Определяю стадию как *{STAGE_LABEL[stage]}* ({STAGE_DESC[stage]}).\n"
            "_Если хотите уточнить — сделаем на Чекапе._",
            parse_mode="Markdown",
        )

    await _send_question(update, context, index=0)


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback quiz:ans:<index>:<score>."""
    query = update.callback_query
    await query.answer()

    parts = (query.data or "").split(":")
    if len(parts) < 4:
        return
    try:
        index = int(parts[2])
        score = int(parts[3])
    except ValueError:
        return

    if index >= len(QUIZ_QUESTIONS):
        return

    answers = context.user_data.setdefault(_KEY_ANS, {})
    answers[QUIZ_QUESTIONS[index].key] = score
    next_index = index + 1
    context.user_data[_KEY_IDX] = next_index

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(session, user_id=user.id, event="quiz_question_answered",
                        payload={"q_key": QUIZ_QUESTIONS[index].key, "score": score})
        await session.commit()

    if next_index < len(QUIZ_QUESTIONS):
        await _send_question(update, context, index=next_index)
    else:
        await _finish(update, context)


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    last_idx = context.user_data.get(_KEY_IDX, 0)
    start_ts = context.user_data.get(_KEY_START)
    duration = int(time.time() - start_ts) if start_ts else None

    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(session, user_id=user.id, event="quiz_abandoned",
                        payload={"last_q_idx": last_idx, "duration_sec": duration})
        await session.commit()

    for k in (_KEY_PHASE, _KEY_IDX, _KEY_ANS, _KEY_SEG, _KEY_P2, _KEY_STAGE, _KEY_CONF, _KEY_START):
        context.user_data.pop(k, None)

    await query.message.reply_text(
        "Прервала. Чтобы вернуться — /quiz",
        reply_markup=keyboards.main_menu(),
    )


async def _finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answers = context.user_data.get(_KEY_ANS, {})
    stage = context.user_data.get(_KEY_STAGE, "team")
    conf = context.user_data.get(_KEY_CONF, "high")
    segment = context.user_data.get(_KEY_SEG, "other")
    start_ts = context.user_data.get(_KEY_START)
    duration = int(time.time() - start_ts) if start_ts else None

    for k in (_KEY_PHASE, _KEY_IDX, _KEY_ANS, _KEY_SEG, _KEY_P2, _KEY_STAGE, _KEY_CONF, _KEY_START):
        context.user_data.pop(k, None)

    result = build_result(answers, stage, segment, stage_confidence=conf)

    # Сохраняем в БД
    async with async_session_factory()() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        user.quiz_score = result.score
        await mark_quiz_completed(
            session,
            user=user,
            score=result.score,
            stage=stage,
            segment=segment,
            layer_scores=dict(result.layer_scores),
            answers=answers,
            growth_points=[
                {"layer": gp.layer, "layer_label": gp.layer_label,
                 "question_key": gp.question_key, "short": gp.short, "action": gp.action}
                for gp in result.growth_points
            ],
            source="bot",
            duration_sec=duration,
        )
        await log_event(session, user_id=user.id, event="quiz_completed",
                        payload={"score": result.score, "stage": stage, "segment": segment,
                                 "layer_scores": dict(result.layer_scores), "duration_sec": duration})
        # lead_stage cold → warm
        if user.lead_stage == "cold":
            user.lead_stage = "warm"
        await session.commit()

    await _send_result(update, result)


async def _send_result(update: Update, result) -> None:
    """Рендеринг результата в 3 сообщения (Telegram ≤4096 символов)."""
    msg = update.effective_message

    # ── Сообщение 1: Score + бенчмарк ────────────────────────────────────
    bm_lines = ""
    if result.benchmark_mean is not None:
        delta = result.benchmark_delta or 0
        delta_sign = "+" if delta >= 0 else ""
        delta_color = "выше" if delta >= 0 else "ниже"
        bm_lines = (
            f"\nСредний для {result.segment_label} на стадии {result.stage_label}: "
            f"*{result.benchmark_mean}*\n"
            f"Δ {delta_sign}{delta} — вы {delta_color} среднего по сегменту"
        )

    conf_note = ""
    if result.stage_confidence == "low":
        conf_note = "\n\n_Стадия определена приближённо — уточним на Чекапе._"

    text1 = (
        f"🎯 *Founder OS Score · {result.score}/100*\n\n"
        f"{result.category}\n\n"
        f"Стадия роста: *{result.stage_label}* ({STAGE_DESC.get(result.stage, '')})\n"
        f"Сегмент: {SEGMENT_DISPLAY.get(result.segment, result.segment)}"
        f"{bm_lines}"
        f"{conf_note}\n\n"
        "_Бенчмарк калибруется — точнее после 100+ клиентов в каждой стадии × сегменте._"
    )
    await msg.reply_text(text1, parse_mode="Markdown")

    # ── Сообщение 2: 4 слоя ───────────────────────────────────────────────
    layer_lines = "\n".join(
        f"{layer_color(score)} {code} · {LAYER_LABEL[code]} — {score}"  # type: ignore[index]
        for code, score in result.layer_scores.items()
    )
    weakest = min(result.layer_scores.items(), key=lambda x: x[1])
    weakest_label = LAYER_LABEL[weakest[0]]

    stage_note = ""
    if result.stage == "structure" and weakest[0] == "03":
        stage_note = (
            "\n\nНа стадии Структура планка по операционке выше — это типовой кризис координации."
        )
    elif result.stage == "team" and weakest[0] == "03":
        stage_note = (
            "\n\nНа стадии Команда операционка — зона роста: команда выросла, ритма ещё нет."
        )

    text2 = (
        f"*Срез по слоям* (0–100, чем выше — тем зрелее):\n\n"
        f"{layer_lines}\n\n"
        f"Самый слабый слой — *{weakest_label}*."
        f"{stage_note}"
    )
    await msg.reply_text(text2, parse_mode="Markdown")

    # ── Сообщение 3: точки роста + CTA ────────────────────────────────────
    gp_lines = "\n\n".join(
        f"{i + 1}. *{gp.short}* ({gp.layer_label})\n   {gp.action}"
        for i, gp in enumerate(result.growth_points)
    )

    text3 = (
        f"*3 точки роста на ближайшие 30 дней:*\n\n"
        f"{gp_lines}\n\n"
        "— — —\n"
        "Хотите глубже? *Бизнес-чекап* — 20 вопросов с цифрами, "
        "PDF 10–15 стр + FigJam-карта за 24 часа."
    )
    markup = _result_keyboard(result)
    await msg.reply_text(text3, parse_mode="Markdown", reply_markup=markup)


def _result_keyboard(result) -> InlineKeyboardMarkup:
    from src.core.config import settings

    cta_map = {
        "audit":                ("📝 Бизнес-чекап · 9 000 ₽", "menu:audit"),
        "audit_plus":           ("🎬 Чекап Plus · 14 000 ₽ — +видео Кати", "menu:audit"),
        "diagnostic_waitlist":  ("📊 Диагностика — лист ожидания", "menu:diagnostic"),
    }
    sec_map = {
        "audit":       ("📝 Бизнес-чекап · 9 000 ₽", "menu:audit"),
        "audit_plus":  ("🎬 Plus · 14 000 ₽ — +видео Кати", "menu:audit"),
        "demo":        ("💬 Сначала поговорить", "menu:demo"),
    }

    p_label, p_cb = cta_map.get(result.cta_primary, cta_map["audit"])
    s_label, s_cb = sec_map.get(result.cta_secondary, sec_map["demo"])

    rows = [
        [InlineKeyboardButton(p_label, callback_data=p_cb)],
        [InlineKeyboardButton(s_label, callback_data=s_cb)],
        [InlineKeyboardButton("← В меню", callback_data="menu:main")],
        keyboards.feedback_row("quiz"),
    ]
    return InlineKeyboardMarkup(rows)
