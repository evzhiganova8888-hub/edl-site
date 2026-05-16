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
    return a


def test_group_answers_sorted_by_order():
    answers = [
        _make_answer("s2", "strategy", 2, "ans2", True),
        _make_answer("s1", "strategy", 1, "ans1", True),
    ]
    grouped = _group_answers(answers)
    assert list(grouped.keys())[0] == "strategy"
    assert grouped["strategy"][0].question_key == "s1"


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
    user = MagicMock()
    user.first_name = "Тест"
    user.last_name = "Тестов"
    user.company_name = "ООО Тест"
    user.segment = "services_it"
    user.email = "test@test.com"

    app = MagicMock()
    app.id = "00000000-0000-0000-0000-000000000001"

    html = render_report(user=user, application=app, answers=[], is_draft=True)
    assert isinstance(html, str)
    assert len(html) > 100
