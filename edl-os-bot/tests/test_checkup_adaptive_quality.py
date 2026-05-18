"""HOT-fix 19.05 — адаптивный quality_check + не-применимо для микро.

См. фидбек Кати после самопрогона: «у меня не было инфы про EBITDA или маржу
за последние 90 дней — мне и моей небольшой компании сейчас не нужна EBITDA».

Тесты гарантируют:
- ответ «не считаю» в финансовом вопросе зачитывается (для микро/малых)
- min_words смягчается на 40% для микро и 20% для малых
- цифра не обязательна в нефинансовых вопросах для микро
- средний и большой бизнес — старые жёсткие пороги
"""
from __future__ import annotations

from src.bot.handlers.checkup import (
    SCALE_MEDIUM,
    SCALE_MICRO,
    SCALE_SMALL,
    _is_not_applicable,
    _quality_check,
    _scale_multiplier,
)
from src.core.checkup_questions import by_key


def _q(key: str):
    return by_key()[key]


# ─── _is_not_applicable ───────────────────────────────────────────────────────


def test_not_applicable_markers():
    assert _is_not_applicable("не считаю проектную маржу") is True
    assert _is_not_applicable("у нас нет данных по EBITDA") is True
    assert _is_not_applicable("это не применимо для нашего масштаба") is True
    assert _is_not_applicable("Не отслеживаю отдельно по проектам") is True
    assert _is_not_applicable("Считаю каждый месяц вручную") is False
    assert _is_not_applicable("") is False


# ─── _scale_multiplier ────────────────────────────────────────────────────────


def test_scale_multiplier_micro_softer():
    assert _scale_multiplier(SCALE_MICRO) == 0.6


def test_scale_multiplier_small_slightly_softer():
    assert _scale_multiplier(SCALE_SMALL) == 0.8


def test_scale_multiplier_medium_default():
    assert _scale_multiplier(SCALE_MEDIUM) == 1.0


def test_scale_multiplier_unknown_default():
    assert _scale_multiplier(None) == 1.0


# ─── _quality_check ───────────────────────────────────────────────────────────


def test_not_applicable_passes_for_finance_micro():
    """Микро-бизнес говорит «не считаю EBITDA» — зачитываем."""
    q = _q("m2_ebitda")
    passed, notes = _quality_check("Не считаю EBITDA отдельно, оборот 5 млн/мес.", q, scale=SCALE_MICRO)
    assert passed is True
    assert any("не применимо" in n for n in notes)


def test_not_applicable_passes_even_for_medium_finance():
    """«Не применимо» работает для финвопросов независимо от scale —
    это сигнал, что у клиента нет данных, не зависит от размера."""
    q = _q("o2_project_margin")
    passed, _ = _quality_check("Не отслеживаем проектную маржу.", q, scale=SCALE_MEDIUM)
    assert passed is True


def test_not_applicable_not_a_pass_for_non_finance():
    """Стратегические/sales вопросы — «не считаю» не достаточно."""
    q = _q("s2_bets")
    passed, _ = _quality_check("Не считаю.", q, scale=SCALE_MICRO)
    assert passed is False


def test_micro_softer_word_count():
    """Микро-бизнес: 15 слов проходят там, где middle требует 25."""
    q = _q("s2_bets")  # min_words=30 → micro_effective=18
    text = " ".join(["слово"] * 18) + " 3 ставки этого года: продажи, найм, продукт"
    passed_micro, _ = _quality_check(text, q, scale=SCALE_MICRO)
    passed_medium, _ = _quality_check(text, q, scale=SCALE_MEDIUM)
    assert passed_micro is True
    assert passed_medium is False


def test_micro_no_digit_required_for_strategy():
    """Микро + нефинансовый вопрос → можно без цифр."""
    q = _q("s4_antipatterns")  # min_words=25 → micro=15
    text = (
        "Анти-паттерн один: пытаемся делать слишком много направлений сразу. "
        "Ловим — еженедельный обзор приоритетов с командой "
        "и решение что НЕ делаем."
    )
    # Нет цифр, но есть >15 слов
    passed, notes = _quality_check(text, q, scale=SCALE_MICRO)
    assert passed is True, f"Expected pass, got notes: {notes}"


def test_micro_digit_still_required_for_finance():
    """Микро в финвопросе — цифра нужна, без неё не зачёт."""
    q = _q("m1_cashflow")
    text = (
        "У нас сейчас есть деньги на счёте, поступают новые платежи, "
        "тратим на зарплаты и налоги, прогноз нормальный."
    )
    passed, notes = _quality_check(text, q, scale=SCALE_MICRO)
    # Цифра отсутствует → not passed
    assert passed is False
    assert any("цифра" in n for n in notes)


def test_medium_strict_word_count():
    """Средний — порог не смягчается, нужно полное число слов."""
    q = _q("s1_horizon")  # min_words=25
    short_text = "Через 3 года — оборот 30 млн, 8 человек."  # 8 слов
    passed, _ = _quality_check(short_text, q, scale=SCALE_MEDIUM)
    assert passed is False


# ─── No anglicisms in example_good (HOT-7) ────────────────────────────────────


FORBIDDEN_ANGLICISMS_IN_EXAMPLES = [
    " SaaS", "Pre-Series", " SMB ", " SDR", " CEO ", " CFO ", " CTO ", " CMO ",
    "Enterprise-", "B2C-", " B2B ", "Tech-lead", "Senior dev", "ramp-up",
    "compensation review", "pipeline-обзор", "onboarding'а", "delivery", "sync ",
    "ADR-шаблон", "Apollo", "Outbound LinkedIn", "Inbound", " ABM", " churn",
    " AOV ", " ARR ", " NPS ", " ICP ",  # с пробелами вокруг — чтобы не ловить в скобках-пояснениях
]


def test_examples_have_no_anglicisms():
    """SoT v1.4 §14.2 запрещает SMB/SaaS/Pre-Series A/AOV без русского перевода.
    Эти термины можно ТОЛЬКО в скобках после русского эквивалента."""
    from src.core.checkup_questions import CHECKUP_QUESTIONS

    findings = []
    for q in CHECKUP_QUESTIONS:
        for token in FORBIDDEN_ANGLICISMS_IN_EXAMPLES:
            if token in q.example_good:
                findings.append(f"{q.key}: {token!r}")
    assert not findings, f"Англицизмы в example_good:\n{findings}"
