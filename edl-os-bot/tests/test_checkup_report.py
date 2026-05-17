"""Checkup report: рендеринг HTML и группировка ответов."""
from unittest.mock import MagicMock

from src.core.checkup_report import _group_answers, _quality_summary, render_report


def _make_answer(key: str, layer: str, order: int, text: str, passed: bool):
    a = MagicMock()
    a.question_key = key
    a.layer = layer
    a.text = text
    a.quality_passed = passed
    a.answered_at = None
    a.quality_notes = None  # Must be None — json.loads(MagicMock()) would fail
    return a


def test_group_answers_sorted_by_order():
    """_group_answers возвращает dict[str, list[dict]], отсортированный по order."""
    # Используем реальные ключи из CHECKUP_QUESTIONS
    answers = [
        _make_answer("s2_bets", "strategy", 2, "ans2", True),
        _make_answer("s1_horizon", "strategy", 1, "ans1", True),
    ]
    grouped = _group_answers(answers)
    assert "strategy" in grouped
    assert len(grouped["strategy"]) == 2
    # Первым должен быть вопрос с меньшим order (s1_horizon = order 1)
    assert grouped["strategy"][0]["order"] == 1
    assert grouped["strategy"][1]["order"] == 2


def test_group_answers_unknown_key_skipped():
    """Ответы с неизвестным question_key должны пропускаться."""
    answers = [
        _make_answer("unknown_key", "strategy", 1, "text", True),
    ]
    grouped = _group_answers(answers)
    assert grouped.get("strategy") == []


def test_quality_summary_counts():
    answers = [
        _make_answer("k1", "strategy", 1, "x", True),
        _make_answer("k2", "strategy", 2, "x", False),
        _make_answer("k3", "sales", 1, "x", True),
    ]
    s = _quality_summary(answers)
    assert s["total"] == 3
    assert s["passed"] == 2
    assert s["failed"] == 1


def test_render_report_returns_html_string():
    """render_report возвращает непустую HTML-строку."""
    user = MagicMock()
    user.first_name = "Тест"
    user.last_name = "Тестов"
    user.company_name = "ООО Тест"
    user.segment = "services_it"
    user.email = "test@test.com"

    app = MagicMock()
    app.id = "00000000-0000-0000-0000-000000000001"
    app.payload = {"plan": "base"}       # render_report accesses application.payload
    app.checkup_completed_at = None

    # render_report не принимает is_draft — убран
    html = render_report(user=user, application=app, answers=[])
    assert isinstance(html, str)
    assert len(html) > 100
    assert "<html" in html or "<!DOCTYPE" in html
