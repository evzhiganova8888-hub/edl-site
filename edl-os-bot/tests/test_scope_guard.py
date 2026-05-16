"""Scope guard: детерминированный whitelist/blacklist фильтр."""
import pytest

from src.core.scope_guard import is_off_topic


@pytest.mark.parametrize("text", [
    "Какой сегодня прогноз погоды?",
    "Биткоин растёт или падает?",
    "Помоги написать код на Python",
    "Как переехать в Европу?",
    "Ставки на спорт, где лучше?",
    "привет",
    "да",
    "расскажи",
])
def test_off_topic_blocked(text: str):
    assert is_off_topic(text) is True, f"Should be blocked: {text!r}"


@pytest.mark.parametrize("text", [
    "Как снизить CAC в воронке продаж для B2B SaaS?",
    "Хочу пройти Чекап — как это работает?",
    "У нас проблемы с маржой на маркетплейсе, EBITDA падает",
    "Какие метрики нужны для стратегического слоя EDL OS?",
    "Как рассчитать ARR и churn для нашего продукта?",
    "Объясни про онбординг команды и ротацию",
    "Нужна ли нам диагностика бизнеса — выручка 50 млн в год",
])
def test_on_topic_allowed(text: str):
    assert is_off_topic(text) is False, f"Should be allowed: {text!r}"


def test_short_query_with_edl_marker_allowed():
    assert is_off_topic("Чекап как работает") is False


def test_long_query_without_markers_blocked():
    words = " ".join(["слово"] * 20)
    assert is_off_topic(words) is True


def test_blacklist_overrides_whitelist():
    # политика — blacklist, но тут есть и маркер EDL (выручка)
    assert is_off_topic("политика влияет на нашу выручку и CAC") is True


# --- §7.5 golden-flow test cases (exact messages from smoke test spec) ---

@pytest.mark.parametrize("text", [
    "Какая погода в Москве?",          # погод → blacklist
    "Биткоин ещё растёт?",             # биткоин → blacklist
    "Как переехать в Грузию?",         # нет whitelist-маркеров, >3 слов
    "Помоги с кодом на Python",        # нет whitelist-маркеров, >3 слов
    "Знаешь хороший рецепт борща?",   # нет whitelist-маркеров, >3 слов
    "Привет",                          # ≤3 слова, нет whitelist-маркера
])
def test_section_7_5_off_topic(text: str):
    """Кейсы из §7.5 ТЗ: должны блокироваться scope_guard."""
    assert is_off_topic(text) is True, f"§7.5: should be blocked: {text!r}"


def test_section_7_5_on_topic():
    """Кейс #7 из §7.5: бизнес-вопрос с маркерами должен пройти в LLM."""
    text = "Как считать маржу по проектам в IT-услугах при выручке 80 млн в год?"
    assert is_off_topic(text) is False, f"§7.5: should be allowed: {text!r}"
