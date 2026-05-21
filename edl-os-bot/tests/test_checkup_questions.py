"""Чекап v2: структура 20 гибридных вопросов (3 MC + 1 numeric + 1 short-text на слой)."""
from src.core.checkup_questions import (
    CHECKUP_QUESTIONS,
    VALID_MC_SCORES,
    by_key,
    by_layer,
    mc_questions,
    numeric_questions,
    short_text_questions,
)


def test_total_20_questions():
    assert len(CHECKUP_QUESTIONS) == 20


def test_four_layers():
    layers = {q.layer for q in CHECKUP_QUESTIONS}
    assert layers == {"01", "02", "03", "04"}


def test_unique_keys():
    keys = [q.key for q in CHECKUP_QUESTIONS]
    assert len(keys) == len(set(keys))


def test_unique_orders_per_layer():
    for layer, questions in by_layer().items():
        orders = [q.order for q in questions]
        assert len(orders) == len(set(orders)), f"Duplicate orders in {layer}"


def test_orders_are_1_to_20():
    orders = sorted([q.order for q in CHECKUP_QUESTIONS])
    assert orders == list(range(1, 21))


def test_5_questions_per_layer():
    for layer, qs in by_layer().items():
        assert len(qs) == 5, f"Layer {layer} has {len(qs)} questions, expected 5"


def test_hybrid_structure_per_layer():
    """В каждом слое: 3 MC + 1 numeric + 1 short-text."""
    for layer in ("01", "02", "03", "04"):
        layer_qs = [q for q in CHECKUP_QUESTIONS if q.layer == layer]
        mc = [q for q in layer_qs if q.answer_type == "mc"]
        num = [q for q in layer_qs if q.answer_type == "numeric"]
        txt = [q for q in layer_qs if q.answer_type == "short_text"]
        assert len(mc) == 3, f"Layer {layer}: expected 3 MC, got {len(mc)}"
        assert len(num) == 1, f"Layer {layer}: expected 1 numeric, got {len(num)}"
        assert len(txt) == 1, f"Layer {layer}: expected 1 short_text, got {len(txt)}"


def test_totals_by_type():
    assert len(mc_questions()) == 12
    assert len(numeric_questions()) == 4
    assert len(short_text_questions()) == 4


def test_mc_options_valid():
    for q in mc_questions():
        assert q.options is not None, f"{q.key} has no MC options"
        assert len(q.options) == 5, f"{q.key} has {len(q.options)} options, expected 5"
        for label, score in q.options:
            assert score in VALID_MC_SCORES, f"{q.key}: score {score} not in {VALID_MC_SCORES}"
            assert label.strip(), f"{q.key}: empty option label"


def test_numeric_has_range_and_unit():
    for q in numeric_questions():
        assert q.numeric_min is not None, f"{q.key} has no numeric_min"
        assert q.numeric_max is not None, f"{q.key} has no numeric_max"
        assert q.numeric_unit, f"{q.key} has no numeric_unit"
        assert q.benchmark_key, f"{q.key} has no benchmark_key"


def test_short_text_has_quality_requirements():
    for q in short_text_questions():
        assert q.min_chars and q.min_chars >= 100, f"{q.key} min_chars too low"
        assert q.min_words and q.min_words >= 20, f"{q.key} min_words too low"
        assert q.example_good and q.example_good.strip(), f"{q.key} empty example_good"
        assert q.expects, f"{q.key} has no expects"


def test_section_break_after_5_10_15():
    """После Q5, Q10, Q15 — section_break_after=True."""
    qs_by_order = {q.order: q for q in CHECKUP_QUESTIONS}
    for order in (5, 10, 15):
        assert qs_by_order[order].section_break_after, f"Q{order} should have section_break_after"
    # Q20 — last, нет section_break после
    assert not qs_by_order[20].section_break_after


def test_v2_keys_present():
    """Ключи c1..c20 присутствуют."""
    keys = {q.key for q in CHECKUP_QUESTIONS}
    expected = {
        "c1_strategy_process", "c2_strategy_alternatives", "c3_strategy_review",
        "c4_founder_time_strategy_pct", "c5_strategy_antipattern",
        "c6_funnel_home", "c7_crm_discipline", "c8_funnel_metrics",
        "c9_lead_to_deal_pct", "c10_main_channel_blocker",
        "c11_regulations", "c12_rhythm", "c13_bus_factor",
        "c14_key_people_hours_per_week", "c15_bottleneck_action",
        "c16_financial_reporting", "c17_unit_economics", "c18_cash_horizon",
        "c19_company_margin_pct", "c20_vat_2026_scenario",
    }
    assert expected <= keys, f"Missing keys: {expected - keys}"


def test_by_key_lookup():
    q = by_key().get("c1_strategy_process")
    assert q is not None
    assert q.layer == "01"
    assert q.answer_type == "mc"


def test_backward_compat_class_alias():
    """`CheckupQuestion = CheckupQuestionV2` alias для старого кода."""
    from src.core.checkup_questions import CheckupQuestion, CheckupQuestionV2
    assert CheckupQuestion is CheckupQuestionV2
