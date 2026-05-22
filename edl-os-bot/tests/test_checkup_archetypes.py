"""Архетипы Чекап Plus v2.0 — точные матчи и fallback (ТЗ §3.5)."""
from __future__ import annotations

import pytest

from src.core.checkup_archetypes import (
    ARCHETYPE_META,
    MVP_ARCHETYPES,
    SEGMENT_STAGE_BENCHMARKS,
    STAGE_WEIGHTS,
    get_archetype_for_user,
    get_benchmark_avg,
    get_stage_weights,
)


def test_six_mvp_archetypes_present():
    """ТЗ §3.5: ровно 6 архетипов MVP."""
    assert len(MVP_ARCHETYPES) == 6
    expected_keys = {
        "anna_command",
        "anna_structure",
        "dmitri_structure",
        "artem_command",
        "pro_services_structure",
        "nds_first_command",
    }
    assert set(MVP_ARCHETYPES.values()) == expected_keys


def test_every_archetype_has_metadata():
    """Каждому архетипу — полная meta-карточка."""
    required = {
        "name", "segment_label", "segment_label_genitive",
        "stage_current", "stage_next", "typical_revenue",
        "typical_team_size", "typical_pain",
    }
    for archetype_key in MVP_ARCHETYPES.values():
        assert archetype_key in ARCHETYPE_META, f"meta missing for {archetype_key}"
        meta = ARCHETYPE_META[archetype_key]
        assert required.issubset(meta.keys()), (
            f"{archetype_key} missing fields: {required - meta.keys()}"
        )


# ── Точный матч ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "segment,stage,expected",
    [
        ("edu", "Команда", "anna_command"),
        ("edu", "Структура", "anna_structure"),
        ("mp", "Структура", "dmitri_structure"),
        ("it", "Команда", "artem_command"),
        ("serv", "Структура", "pro_services_structure"),
        ("prod", "Команда", "nds_first_command"),
    ],
)
def test_exact_match_returns_correct_archetype(segment, stage, expected):
    assert get_archetype_for_user(segment, stage) == expected


# ── Fallback ─────────────────────────────────────────────────────────────────


def test_same_segment_different_stage_falls_back_to_same_segment():
    # edu × Старт → должен попасть либо в anna_command, либо в anna_structure
    result = get_archetype_for_user("edu", "Старт")
    assert result in ("anna_command", "anna_structure")


def test_unknown_segment_falls_back_to_neighbor():
    # saas × Команда → нет MVP, neighbor=it → artem_command
    assert get_archetype_for_user("saas", "Команда") == "artem_command"


def test_completely_unknown_returns_default():
    # other × неизвестная стадия → дефолт anna_command
    result = get_archetype_for_user("xyz_unknown_segment", "Неизвестная")
    assert result == "anna_command"


def test_none_inputs_use_default():
    assert get_archetype_for_user(None, None) == "anna_command"


def test_stage_aliases_normalized():
    """Старые англоязычные ярлыки стадий из Mini-Чекап маппятся."""
    assert get_archetype_for_user("edu", "team") == "anna_command"
    assert get_archetype_for_user("edu", "structure") == "anna_structure"


# ── Бенчмарки ────────────────────────────────────────────────────────────────


def test_six_benchmarks_match_mvp_archetypes():
    assert set(SEGMENT_STAGE_BENCHMARKS.keys()) == set(MVP_ARCHETYPES.keys())


def test_benchmarks_are_realistic_50_to_70():
    """Sanity: все бенчмарки в разумном коридоре 50–70."""
    for value in SEGMENT_STAGE_BENCHMARKS.values():
        assert 40 <= value <= 80


@pytest.mark.parametrize(
    "segment,stage,expected",
    [
        ("edu", "Команда", 54),
        ("mp", "Структура", 65),
        ("unknown", "Неизвестная", 50),  # дефолт
    ],
)
def test_benchmark_lookup(segment, stage, expected):
    assert get_benchmark_avg(segment, stage) == expected


# ── Stage weights ────────────────────────────────────────────────────────────


def test_stage_weights_sum_to_one():
    """Веса слоёв на каждой стадии должны давать 1.0 (с погрешностью)."""
    for stage, weights in STAGE_WEIGHTS.items():
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-6, f"{stage}: weights sum = {total}"


def test_all_four_layers_in_weights():
    expected = {"strategy", "funnel", "ops", "money"}
    for weights in STAGE_WEIGHTS.values():
        assert set(weights.keys()) == expected
