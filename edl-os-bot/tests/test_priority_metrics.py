"""21-й уточняющий вопрос: парсер + валидация priority_metrics."""
from __future__ import annotations

from src.core.priority_metrics import (
    PROMPT_TEXT,
    RETRY_TEXT,
    looks_like_metric,
    parse_metrics,
    validate_metrics,
)


# ─── parse_metrics ────────────────────────────────────────────────────────────


def test_parse_comma_separated():
    assert parse_metrics("выручка, маржа, cash") == ["выручка", "маржа", "cash"]


def test_parse_slash_separated():
    assert parse_metrics("выручка / маржа / cash") == ["выручка", "маржа", "cash"]


def test_parse_arrow_separated():
    assert parse_metrics("выручка → маржа → cash") == ["выручка", "маржа", "cash"]


def test_parse_numbered_list():
    assert parse_metrics("1) выручка 2) маржа 3) cash") == ["выручка", "маржа", "cash"]


def test_parse_with_i_separator():
    """Слово «и» как разделитель только если окружено пробелами."""
    out = parse_metrics("выручка и маржа")
    assert "выручка" in out
    assert "маржа" in out


def test_parse_empty():
    assert parse_metrics("") == []


def test_parse_dedupes_preserving_order():
    assert parse_metrics("выручка, маржа, выручка") == ["выручка", "маржа"]


def test_parse_strips_punctuation():
    out = parse_metrics("  выручка ,  маржа.  ")
    assert out == ["выручка", "маржа"]


# ─── looks_like_metric ────────────────────────────────────────────────────────


def test_looks_like_metric_known_keyword():
    assert looks_like_metric("выручка") is True
    assert looks_like_metric("CAC") is True
    assert looks_like_metric("retention") is True
    assert looks_like_metric("NPS") is True


def test_looks_like_metric_with_number_unit():
    assert looks_like_metric("loaded 80%") is True
    assert looks_like_metric("3 млн ₽") is True


def test_looks_like_metric_garbage():
    assert looks_like_metric("звонки клиентам") is False
    assert looks_like_metric("работать лучше") is False
    assert looks_like_metric("") is False


# ─── validate_metrics ─────────────────────────────────────────────────────────


def test_validate_ok():
    status, _ = validate_metrics(["выручка", "маржа", "cash"])
    assert status == "ok"


def test_validate_too_few():
    status, _ = validate_metrics(["выручка"])
    assert status == "too_few"


def test_validate_empty():
    status, _ = validate_metrics([])
    assert status == "too_few"


def test_validate_too_many():
    status, _ = validate_metrics(["a", "b", "c", "d", "e", "f"])
    assert status == "too_many"


def test_validate_not_metrics():
    status, _ = validate_metrics(["работать лучше", "звонки", "встречи"])
    assert status == "not_metrics"


def test_validate_caps_at_5():
    status, normalized = validate_metrics(
        ["выручка", "маржа", "cash", "retention", "CAC"]
    )
    assert status == "ok"
    assert len(normalized) == 5


# ─── prompts ──────────────────────────────────────────────────────────────────


def test_prompt_mentions_three_metrics():
    assert "3" in PROMPT_TEXT and ("метри" in PROMPT_TEXT.lower())


def test_retry_text_is_softer():
    """Retry должен объяснять что такое метрика, а не ругать."""
    assert "метрик" in RETRY_TEXT.lower()
    assert "ещё раз" in RETRY_TEXT.lower() or "ещё" in RETRY_TEXT.lower()


def test_prompt_not_numbered_as_21():
    """Методологически Founder OS = 20 вопросов. 21-й не нумеруется."""
    assert "21" not in PROMPT_TEXT
    assert "21" not in RETRY_TEXT
