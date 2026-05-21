"""Регрессия: гарантия возврата нигде не описана как «безусловная».

После сессии 21.05.2026 политика изменена: возврат — условный, работает
только при выполнении ОБОИХ условий (рубрика качества ответов И
невозможность реализовать ни одну рекомендацию). Юрист подтвердил, что
прежняя «безусловная» формулировка создаёт юридический риск.

Этот тест защищает от возврата старой формулировки в будущих PR.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Файлы, по которым проходим scan. Юридический текст «ИП Жиганова
# Екатерина Викторовна» — это идентификатор юр.лица, его не трогаем.
SURFACES = [
    "src/bot/texts.py",
    "src/bot/handlers/refund.py",
    "src/bot/handlers/checkup.py",
    "src/bot/handlers/audit.py",
    "src/core/offer.py",
    "src/knowledge_base/05_refund_guarantee.md",
    "src/knowledge_base/06_objections_handling.md",
    "src/knowledge_base/07_faq.json",
    "src/knowledge_base/02_products_pricing.md",
    "src/knowledge_base/08_checkup_quality_rubric.md",
    "src/prompts/base.md",
    "src/templates/checkup_report.html",
    "src/templates/checkup_report_v2.html",
]

FORBIDDEN_REFUND_PHRASES = [
    "безусловно",
    "безусловная гарантия",
    "безусловного",
    "безусловной",
    "безусловный",
    "без вопросов",
    "без условий",
    "без задержек",
    "причину указывать не надо",
    "причину указывать не нужно",
    "Причину указывать не нужно",
    "Причину указывать не обязательно",
    "причину указывать не обязательно",
    "один клик `/refund`, причину",
    "один клик /refund, причину",
    "Возврат 100%:",
]


@pytest.mark.parametrize("relpath", SURFACES)
def test_no_unconditional_refund_phrases(relpath: str) -> None:
    path = ROOT / relpath
    if not path.exists():
        pytest.skip(f"{relpath} not present")
    content = path.read_text(encoding="utf-8").lower()
    found = [p for p in FORBIDDEN_REFUND_PHRASES if p.lower() in content]
    assert not found, (
        f"{relpath} contains forbidden unconditional refund language: {found}.\n"
        "Use the conditional formulation: возврат при двух условиях — "
        "(1) ответы прошли рубрику качества; (2) ни одну рекомендацию "
        "нельзя реализовать."
    )


def test_kb_refund_guarantee_states_both_conditions():
    """Главный KB-файл должен явно перечислить ОБА условия."""
    text = (ROOT / "src/knowledge_base/05_refund_guarantee.md").read_text(
        encoding="utf-8"
    ).lower()
    assert "рубрик" in text, "должно быть упоминание рубрики качества"
    assert "рекоменда" in text, "должно быть упоминание рекомендаций"
    assert "оба" in text or "обоих" in text, "должна быть фраза про оба условия"


def test_faq_explains_conditional_guarantee():
    raw = (ROOT / "src/knowledge_base/07_faq.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    # Ищем ответ на «Какие гарантии?»
    guarantee_q = next(
        (item for item in data if "гарант" in item["question"].lower()), None
    )
    assert guarantee_q is not None
    answer = guarantee_q["answer"].lower()
    assert "рубрик" in answer or "качеств" in answer
    assert "рекоменда" in answer


def test_texts_guarantee_short_mentions_both_conditions():
    from src.bot.texts import GUARANTEE_SHORT

    txt = GUARANTEE_SHORT.lower()
    assert "рубрик" in txt
    assert "рекоменда" in txt
