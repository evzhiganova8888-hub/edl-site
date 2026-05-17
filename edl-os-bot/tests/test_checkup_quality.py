"""Проверка рубрики качества ответов Чекапа (_quality_check из §6.2 ТЗ).

Тест-кейсы взяты дословно из §6.2 qa_pr18_to_10_of_10.md.
Требует Python 3.12+ (dataclass slots=True в CheckupQuestion).
"""
import pytest

from src.bot.handlers.checkup import _quality_check
from src.core.checkup_questions import by_key


# ─── Тест-кейсы из §6.2 ТЗ ───────────────────────────────────────────────────

@pytest.mark.parametrize("text, expected_pass", [
    # Длиннее min_words (≥25), есть цифра → True
    (
        "Через 3 года SaaS с ARR 120 млн, команда 25 человек, продукт три тарифа в РФ и СНГ "
        "для маркетинговых агентств с выручкой от 50 до 500 млн рублей в год.",
        True,
    ),
    # Короткий, нет цифры → False
    (
        "Не знаю, как-то так.",
        False,
    ),
    # Длиннее min_words, нет цифры → False
    (
        "Растём активно, планы амбициозные, всё будет хорошо, верим в успех, идём вперёд, "
        "команда сильная, продукт уникальный, рынок большой, выручка растёт, конкуренты слабые.",
        False,
    ),
    # Короткий, есть цифра → False
    (
        "ARR 5М.",
        False,
    ),
])
def test_quality_check_s1(text: str, expected_pass: bool):
    """Параметризованные кейсы для вопроса s1_horizon."""
    q = by_key()["s1_horizon"]
    passed, _ = _quality_check(text, q)
    assert passed is expected_pass, (
        f"s1_horizon: expected passed={expected_pass}, got {passed!r} for text={text[:60]!r}"
    )


# ─── Проверка всех четырёх сценариев рубрики (generic) ────────────────────────

def test_quality_all_bad(mocker):
    """Короче min_words И нет цифры → False + 2 labels."""
    q = by_key()["s1_horizon"]  # min_words=25
    short_no_digit = "Не знаю."
    passed, missing = _quality_check(short_no_digit, q)
    assert passed is False
    assert len(missing) == 2
    assert any("слов" in m for m in missing)
    assert any("цифра" in m for m in missing)


def test_quality_long_no_digit():
    """Длиннее min_words, нет цифры → False + только 'цифра'."""
    q = by_key()["s1_horizon"]  # min_words=25
    long_no_digit = " ".join(["слово"] * 30)  # 30 слов, нет цифр
    passed, missing = _quality_check(long_no_digit, q)
    assert passed is False
    assert len(missing) == 1
    assert "цифра" in missing[0]


def test_quality_short_with_digit():
    """Короче min_words, есть цифра → False + только 'слов'."""
    q = by_key()["s1_horizon"]  # min_words=25
    short_with_digit = "ARR 5М выручки 10М."
    passed, missing = _quality_check(short_with_digit, q)
    assert passed is False
    assert len(missing) == 1
    assert "слов" in missing[0]


def test_quality_exact_min_words_with_digit():
    """Ровно min_words с одной цифрой → True (пограничный кейс)."""
    q = by_key()["s1_horizon"]  # min_words=25
    # генерируем строку ровно из 24 слов без цифр + 1 слово с цифрой = 25 слов
    words = ["слово"] * 24 + ["выручка100М"]
    text = " ".join(words)
    assert len(text.split()) == 25
    passed, missing = _quality_check(text, q)
    assert passed is True
    assert missing == []


def test_quality_fully_passed():
    """Длиннее min_words, есть цифра → True, missing=[]."""
    q = by_key()["s1_horizon"]  # min_words=25
    good = (
        "Через 3 года — SaaS для маркетинговых агентств в РФ и СНГ, ARR 120 млн ₽, "
        "команда 25 человек, продукт — три тарифа, ICP — агентства с выручкой "
        "50–500 млн ₽/год. NPS 50, churn ≤ 6% годовых."
    )
    passed, missing = _quality_check(good, q)
    assert passed is True
    assert missing == []
