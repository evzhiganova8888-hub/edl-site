"""SPIN-Чекап v2.0 FSM (ТЗ Чекап Plus v2.0 §3–§4).

Альтернативный flow для 16 SPIN-вопросов. Активируется через
feature-flag `CHECKUP_SPIN_V2_ENABLED` (env или DB FeatureFlag).

Главные отличия от старого 20-quiz FSM:
- 16 вопросов open-text вместо 20 hybrid (MC + numeric + short_text).
- 3 экрана-вставки между блоками слоёв (ТЗ §3.4).
- Чекпоинт после каждого слоя.
- Pause/resume через `Application.checkup_current_question_index`
  (тот же канал, что у v2 — сохранение прогресса).
- «Не знаю / не считаем» → валидный ответ с флагом `is_decline=true`,
  не пропуск.

Что в этом модуле НЕТ (отложено в следующую сессию):
- 5-минутный fail-safe «нет ввода» — требует PTB JobQueue setup.
- Замена /checkup команды — функции экспортируются для будущей wire-up
  в `bot/handlers/checkup.py:checkup_command`.

Использование:
    from src.bot.handlers.checkup_spin import (
        start_spin_checkup,  # вызывается из /checkup при включённом флаге
        handle_spin_text,    # FSM-роутер для текстовых ответов
        handle_spin_callback,  # callback-роутер для кнопок
    )
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.core.checkup_archetypes import ARCHETYPE_META, get_archetype_for_user
from src.core.checkup_spin_questions import (
    LAYER_LABELS,
    SPIN_QUESTIONS,
    get_question_by_index,
    is_decline_answer,
    total_questions,
)
from src.db.models import Application, CheckupAnswer, User
from src.db.repos import get_or_create_user, log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

# ── FSM keys в context.user_data ─────────────────────────────────────────────
KEY_SPIN_APP_ID = "spin_app_id"
KEY_SPIN_STATE = "spin_state"
KEY_SPIN_Q_IDX = "spin_q_idx"
KEY_SPIN_AWAITING_INSERT = "spin_awaiting_insert"  # bool

STATE_AWAIT_START = "await_start"
STATE_AWAIT_ANSWER = "await_answer"
STATE_AWAIT_AFTER_INSERT = "await_after_insert"
STATE_DONE = "done"


# ── Тексты-вставки между блоками (ТЗ §3.4) ──────────────────────────────────


def _insert_text_strategy_to_funnel(archetype: str, meta: dict[str, str]) -> str:
    return (
        f"Прежде чем перейти к Воронке — типичная история для "
        f"{meta['segment_label_genitive']} на стадии {meta['stage_current']}.\n\n"
        "В стратегии ICP часто сформулирован чётко: узкий сегмент с "
        "конкретными характеристиками. В рекламных креативах же — широкое "
        "позиционирование. В лендинге — ещё шире.\n\n"
        "Это три разных адресата. Лиды, привлечённые широкой формулировкой, "
        "не подходят под узкий ICP — отдел продаж это видит и закономерно "
        "их теряет. Так теряется до 35% маркетингового бюджета.\n\n"
        "Сейчас спросим про вашу Воронку."
    )


def _insert_text_funnel_to_ops(archetype: str, meta: dict[str, str]) -> str:
    return (
        f"Прежде чем перейти к Операционке — что мы часто видим в "
        f"{meta['segment_label_genitive']} с командой 10–25 человек.\n\n"
        "Воронка генерит лидов, отдел продаж их обрабатывает — а продуктовая "
        "команда не знает, кому именно она работает. Информация о клиенте "
        "остаётся в голове менеджера или в карточке CRM, до того, кто будет "
        "обслуживать клиента, не доходит.\n\n"
        "В результате: первые 20–30 минут уходят на «знакомство», вместо "
        "пользы клиенту. Это и есть разрыв Воронка → Операционка.\n\n"
        "Сейчас спросим вашу Операционку."
    )


def _insert_text_ops_to_money(archetype: str, meta: dict[str, str]) -> str:
    return (
        f"Перед последним блоком — что мы часто видим в финансах "
        f"{meta['segment_label_genitive']} на стадии {meta['stage_current']}.\n\n"
        "ФОТ растёт быстрее, чем выручка. Команда увеличивается за 6 месяцев "
        "на +12%, выручка только на +7%. Маржа теряет 2–3 п.п. в год — "
        "незаметно в моменте, но накопительно за 2 года это 5–6% маржи "
        "компании.\n\n"
        "Причина — отсутствие правила «новый ФОТ только при росте выручки "
        "на эквивалент». Сейчас спросим ваши Деньги."
    )


_INSERT_TEXTS = {
    # Ключ — это `new_idx` после инкремента: q_idx=3 (Q1.4) → new_idx=4.
    4: _insert_text_strategy_to_funnel,   # после Q1.4 (4 ответа по Стратегии)
    8: _insert_text_funnel_to_ops,        # после Q2.4 (8 ответов по Стратегии+Воронке)
    12: _insert_text_ops_to_money,         # после Q3.4
}


# ── Главные точки входа ──────────────────────────────────────────────────────


async def start_spin_checkup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Запуск нового SPIN-Чекапа. Вызывается из /checkup при включённом флаге.

    Создаёт/находит paid Application, выставляет archetype + report_id,
    отправляет welcome из ТЗ §4.1 и показывает Q1.1.
    """
    tg_user = update.effective_user
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=tg_user.id)
        app = await _find_paid_application(session, user)
        if app is None:
            await update.effective_message.reply_text(
                "Чтобы пройти Бизнес-чекап, сначала нужно оформить покупку.\n\n"
                "9 000 ₽ за Base · 14 000 ₽ за Plus (с видео-разбором от "
                "команды EDL OS).\nГарантия 14 дней — условная (см. /faq)."
            )
            return

        # Восстановление: если q_idx уже > 0, спрашиваем — продолжить или начать заново
        current_idx = app.checkup_current_question_index or 0
        if current_idx > 0 and current_idx < total_questions():
            context.user_data[KEY_SPIN_APP_ID] = str(app.id)
            await session.commit()
            await _send_resume_offer(update, current_idx)
            return

        # Свежий старт — выставим archetype + report_id
        if not app.archetype:
            app.archetype = get_archetype_for_user(user.segment, user.stage)
        if not app.report_id:
            app.report_id = _generate_report_id(app)
        app.checkup_started_at = app.checkup_started_at or datetime.now(timezone.utc)
        app.checkup_current_question_index = 0

        await log_event(
            session,
            user_id=user.id,
            event="spin_checkup_started",
            payload={
                "application_id": str(app.id),
                "archetype": app.archetype,
                "report_id": app.report_id,
            },
        )
        await session.commit()

        context.user_data[KEY_SPIN_APP_ID] = str(app.id)
        context.user_data[KEY_SPIN_Q_IDX] = 0
        context.user_data[KEY_SPIN_STATE] = STATE_AWAIT_START

    await _send_welcome(update, plan=_plan_of(app))


async def handle_spin_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Callback-роутер для кнопок SPIN. Pattern: `spin:*`.

    Возвращает True если обработано (callback consumed), иначе False.
    """
    query = update.callback_query
    if not query or not query.data:
        return False
    parts = query.data.split(":")
    if parts[0] != "spin":
        return False
    await query.answer()
    action = parts[1] if len(parts) > 1 else ""

    if action == "begin":
        # «Начать» с экрана welcome
        await _send_current_question(update, context)
        return True
    if action == "continue":
        # «Понял, продолжаем» после вставки или чекпоинта
        await _send_current_question(update, context)
        return True
    if action == "resume":
        # «Продолжить» с того места
        await _send_current_question(update, context)
        return True
    if action == "restart":
        # «Начать заново» — обнуляем q_idx и архивируем старые ответы
        await _restart_spin(update, context)
        return True
    if action == "pause":
        await query.message.reply_text(
            "Пауза принята. Прогресс сохранён.\n"
            "Команда /checkup — продолжить с того места."
        )
        return True
    return False


async def handle_spin_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """FSM-роутер для свободного текста. Возвращает True если в SPIN-флоу.

    Вызывается из `bot.handlers.dialog.handle_text` перед общим LLM-fallback.
    """
    app_id_str = context.user_data.get(KEY_SPIN_APP_ID)
    state = context.user_data.get(KEY_SPIN_STATE)
    if not app_id_str or state != STATE_AWAIT_ANSWER:
        return False

    try:
        app_uuid = UUID(app_id_str)
    except (ValueError, TypeError):
        # Защита от поломанного state
        context.user_data.pop(KEY_SPIN_APP_ID, None)
        context.user_data.pop(KEY_SPIN_STATE, None)
        return False

    answer_text = (update.effective_message.text or "").strip()
    if not answer_text:
        return False

    # Команды pause/resume в свободном тексте (ТЗ §3.6)
    if answer_text.lower() in {"пауза", "прервать", "остановить", "стоп"}:
        await update.effective_message.reply_text(
            "Пауза принята. Прогресс сохранён. "
            "Команда /checkup — продолжить с того места."
        )
        return True

    is_decline, decline_marker = is_decline_answer(answer_text)
    q_idx = context.user_data.get(KEY_SPIN_Q_IDX, 0)
    question = get_question_by_index(q_idx)
    if question is None:
        return False

    factory = async_session_factory()
    async with factory() as session:
        # Сохраняем ответ (upsert)
        existing = (
            await session.execute(
                select(CheckupAnswer)
                .where(CheckupAnswer.application_id == app_uuid)
                .where(CheckupAnswer.question_key == question.id)
            )
        ).scalar_one_or_none()
        word_count = len(answer_text.split())
        # quality_passed: для SPIN считаем «прошёл» если есть конкретика
        # (>=25 слов ИЛИ цифра, ИЛИ это decline). Финальный скоринг — в Claude.
        has_digit = any(c.isdigit() for c in answer_text)
        quality_passed = bool(is_decline or word_count >= 25 or has_digit)

        if existing:
            existing.text = answer_text
            existing.word_count = word_count
            existing.quality_passed = quality_passed
            existing.answer_type = "spin"
            existing.is_decline = is_decline
            existing.decline_reason = decline_marker
            existing.answered_at = datetime.now(timezone.utc)
        else:
            app = await session.get(Application, app_uuid)
            user_id = app.user_id if app else None
            session.add(
                CheckupAnswer(
                    application_id=app_uuid,
                    user_id=user_id,
                    question_key=question.id,
                    layer=question.layer,
                    text=answer_text,
                    word_count=word_count,
                    quality_passed=quality_passed,
                    answer_type="spin",
                    is_decline=is_decline,
                    decline_reason=decline_marker,
                )
            )

        # Обновляем прогресс
        app = await session.get(Application, app_uuid)
        new_idx = q_idx + 1
        if app:
            app.checkup_current_question_index = new_idx
            app.checkup_last_active_at = datetime.now(timezone.utc)
        await log_event(
            session,
            user_id=app.user_id if app else None,
            event="spin_answer_saved",
            payload={
                "question_key": question.id,
                "q_idx": q_idx,
                "is_decline": is_decline,
                "word_count": word_count,
            },
        )
        await session.commit()
        plan = _plan_of(app)
        archetype = (app.archetype if app else "anna_command") or "anna_command"

    context.user_data[KEY_SPIN_Q_IDX] = new_idx

    # После Q1.4 / Q2.4 / Q3.4 — чекпоинт + вставка
    if new_idx in _INSERT_TEXTS:
        await _send_checkpoint_and_insert(
            update, context, layer_completed_idx=new_idx, archetype=archetype
        )
        return True

    # После Q4.4 — финальный экран
    if new_idx >= total_questions():
        await _send_completion(update, context, app_uuid=app_uuid, plan=plan)
        return True

    # Следующий вопрос
    await _send_current_question(update, context)
    return True


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _find_paid_application(session, user: User) -> Application | None:
    result = await session.execute(
        select(Application)
        .where(Application.user_id == user.id)
        .where(Application.type == "audit")
        .where(Application.status == "paid")
        .order_by(Application.payment_succeeded_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _plan_of(app: Application | None) -> str:
    if app is None:
        return "basic"
    payload = app.payload or {}
    return "plus" if payload.get("plan") == "plus" else "basic"


def _generate_report_id(app: Application) -> str:
    """Формат `EDL-CHK-YYYY-NNNN` (NNNN — короткий random hex для пилота)."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(2).upper()
    inv = getattr(app, "inv_id", None)
    if inv is not None:
        return f"EDL-CHK-{year}-{int(inv):04d}"
    return f"EDL-CHK-{year}-{suffix}"


async def _send_welcome(update: Update, *, plan: str) -> None:
    """Welcome из ТЗ §4.1. Тарифная вариация: Plus добавляет упоминание видео."""
    video_line = (
        "Через 24 часа после PDF — 15-минутный видео-разбор от команды EDL OS.\n"
        if plan == "plus"
        else ""
    )
    text = (
        "Спасибо за оплату. Открываю Бизнес-чекап.\n\n"
        "Это 16 диагностических вопросов по 4 слоям: Стратегия → Воронка → "
        "Операционка → Деньги. На каждый вопрос — короткий контекст и точный "
        "запрос. От зрелого собственника ждём 3–5 предложений с цифрами.\n\n"
        "Что важно знать перед началом:\n"
        "• Время — примерно 60 минут. Возможны паузы на проверку цифр в "
        "1С / CRM / банке.\n"
        "• Пропустить вопросы нельзя — но прервать и вернуться можно в любой "
        "момент, прогресс сохранится (напишите «пауза»).\n"
        "• Если действительно не знаете ответ — напишите «не знаю» / "
        "«не считаем». Это валидный ответ, мы это учтём в отчёте.\n"
        "• Лучше один точный ответ, чем три быстрых.\n\n"
        "Через ~3 минуты после последнего ответа PDF придёт в этот чат.\n"
        f"{video_line}\n"
        "Гарантия возврата 14 дней — *условная*. Подробности — /faq.\n\n"
        "— команда EDL OS"
    )
    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Начать Чекап", callback_data="spin:begin")],
        ]),
    )


async def _send_resume_offer(update: Update, current_idx: int) -> None:
    """Если у Application уже есть прогресс — предлагаем продолжить."""
    q = get_question_by_index(current_idx)
    layer_label = LAYER_LABELS.get(q.layer, "—") if q else "—"
    await update.effective_message.reply_text(
        f"Вы остановились на вопросе {current_idx + 1}/{total_questions()} "
        f"(слой {layer_label}). Продолжим?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("▶ Продолжить", callback_data="spin:resume")],
            [InlineKeyboardButton("↺ Начать заново", callback_data="spin:restart")],
        ]),
    )


async def _restart_spin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Архивируем ответы и обнуляем q_idx."""
    app_id_str = context.user_data.get(KEY_SPIN_APP_ID)
    if not app_id_str:
        return
    try:
        app_uuid = UUID(app_id_str)
    except (ValueError, TypeError):
        return
    factory = async_session_factory()
    async with factory() as session:
        app = await session.get(Application, app_uuid)
        if app:
            app.checkup_current_question_index = 0
            app.checkup_started_at = datetime.now(timezone.utc)
        # Удаляем существующие SPIN-ответы (есть UNIQUE constraint app+q_key)
        from sqlalchemy import delete
        await session.execute(
            delete(CheckupAnswer)
            .where(CheckupAnswer.application_id == app_uuid)
            .where(CheckupAnswer.answer_type == "spin")
        )
        await log_event(
            session,
            user_id=app.user_id if app else None,
            event="spin_checkup_restarted",
            payload={"application_id": app_id_str},
        )
        await session.commit()
    context.user_data[KEY_SPIN_Q_IDX] = 0
    context.user_data[KEY_SPIN_STATE] = STATE_AWAIT_START
    await update.effective_message.reply_text(
        "Хорошо, начинаем заново.",
    )
    await _send_current_question(update, context)


async def _send_current_question(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Показать SPIN-вопрос с прогресс-баром (ТЗ §4.2)."""
    q_idx = context.user_data.get(KEY_SPIN_Q_IDX, 0)
    question = get_question_by_index(q_idx)
    if question is None:
        return

    total = total_questions()
    filled = "▰" * (q_idx + 1)
    empty = "▱" * (total - q_idx - 1)
    progress_pct = round((q_idx + 1) / total * 100)

    text = (
        f"*Вопрос {q_idx + 1}/{total}* · {filled}{empty} {progress_pct}%\n\n"
        f"_{question.situation}_\n\n"
        f"*{question.problem}*\n\n"
        f"Жду ваш ответ одним сообщением. Не торопитесь — прогресс сохраняется. "
        f"Если нужна пауза — напишите «пауза»."
    )
    context.user_data[KEY_SPIN_STATE] = STATE_AWAIT_ANSWER
    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown",
    )


async def _send_checkpoint_and_insert(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    layer_completed_idx: int,
    archetype: str,
) -> None:
    """Чекпоинт после слоя + текст-вставка с архетипической историей.

    `layer_completed_idx` — индекс ПОСЛЕ обработки последнего вопроса слоя
    (4 = после Q1.4, 8 = после Q2.4, 12 = после Q3.4).
    """
    insert_fn = _INSERT_TEXTS.get(layer_completed_idx)
    if insert_fn is None:
        # Нет вставки для этого индекса — просто следующий вопрос
        await _send_current_question(update, context)
        return

    meta = ARCHETYPE_META.get(archetype, ARCHETYPE_META["anna_command"])  # type: ignore[index]
    insert_text = insert_fn(archetype, meta)

    # Сначала чекпоинт (ТЗ §4.3)
    layer_just_done = {
        4: "01 СТРАТЕГИЯ", 8: "02 ВОРОНКА", 12: "03 ОПЕРАЦИОНКА",
    }.get(layer_completed_idx, "—")
    next_layer = {
        4: "Воронке", 8: "Операционке", 12: "Деньгам",
    }.get(layer_completed_idx, "—")

    checkpoint = (
        f"✓ 4 вопроса по слою {layer_just_done} — готовы.\n\n"
        f"Перед переходом к {next_layer} — короткий контекст того, что мы "
        f"часто видим у бизнесов вашего сегмента и стадии."
    )
    await update.effective_message.reply_text(
        checkpoint,
    )
    await update.effective_message.reply_text(
        insert_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Понял, продолжаем", callback_data="spin:continue")],
            [InlineKeyboardButton("⏸ Сделать паузу", callback_data="spin:pause")],
        ]),
    )
    context.user_data[KEY_SPIN_STATE] = STATE_AWAIT_AFTER_INSERT


async def _send_completion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    app_uuid: UUID,
    plan: str,
) -> None:
    """Финальный экран после Q4.4 и запуск PDF-генерации (ТЗ §4.4)."""
    factory = async_session_factory()
    async with factory() as session:
        app = await session.get(Application, app_uuid)
        if app:
            app.checkup_completed_at = datetime.now(timezone.utc)
        await log_event(
            session,
            user_id=app.user_id if app else None,
            event="spin_checkup_completed",
            payload={"application_id": str(app_uuid), "plan": plan},
        )
        await session.commit()

    context.user_data[KEY_SPIN_STATE] = STATE_DONE
    context.user_data.pop(KEY_SPIN_APP_ID, None)
    context.user_data.pop(KEY_SPIN_Q_IDX, None)

    video_line = (
        "T+24 ч (Plus): персональный видео-разбор от команды EDL OS.\n"
        "T+48 ч (Plus): купон −20% на Диагностику с окном 24 часа.\n"
        if plan == "plus"
        else ""
    )

    await update.effective_message.reply_text(
        "Готово. 16 ответов получены.\n\n"
        "Что происходит дальше:\n"
        "• T+0 (сейчас): анализатор обрабатывает ваши ответы.\n"
        "• T+3 мин: PDF в этом чате + ссылка на S3.\n"
        f"{video_line}"
        "\nЭто лучшее время выпить кофе. Спасибо за доверие.\n— команда EDL OS",
    )

    # Запуск генерации PDF (best-effort)
    try:
        from src.tasks.generate_checkup_pdf import generate_checkup_pdf
        # Поддерживаем как Celery (.delay), так и fallback-stub
        getattr(generate_checkup_pdf, "delay", lambda *a, **kw: None)(str(app_uuid))
    except Exception:
        logger.exception("Failed to enqueue PDF generation for %s", app_uuid)
