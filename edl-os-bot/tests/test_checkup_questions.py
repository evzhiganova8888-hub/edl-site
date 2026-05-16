"""Checkup questions: структура 20 вопросов, 4 слоя, уникальность ключей."""
from src.core.checkup_questions import CHECKUP_QUESTIONS, by_key, by_layer


def test_total_20_questions():
    assert len(CHECKUP_QUESTIONS) == 20


def test_four_layers():
    layers = {q.layer for q in CHECKUP_QUESTIONS}
    assert layers == {"strategy", "sales", "operations", "finance"}


def test_unique_keys():
    keys = [q.key for q in CHECKUP_QUESTIONS]
    assert len(keys) == len(set(keys))


def test_unique_orders_per_layer():
    for layer, questions in by_layer().items():
        orders = [q.order for q in questions]
        assert len(orders) == len(set(orders)), f"Duplicate orders in {layer}"


def test_by_key_lookup():
    q = by_key().get("s1_horizon")
    assert q is not None
    assert q.layer == "strategy"
    assert q.min_words >= 20


def test_min_words_positive():
    for q in CHECKUP_QUESTIONS:
        assert q.min_words > 0, f"{q.key} has min_words=0"


def test_example_good_not_empty():
    for q in CHECKUP_QUESTIONS:
        assert q.example_good.strip(), f"{q.key} has empty example_good"
