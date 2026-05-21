"""Чекап v2: проверка PDF блоков — 3 agent teaser + CTA + video scripts."""
from src.core.checkup_pdf_blocks import (
    DIAGNOSTIC_PRICE_RUB,
    analyst_agent_teaser,
    build_three_teasers,
    diagnostic_cta_block,
    monitor_agent_teaser,
    writer_agent_teaser,
)
from src.core.checkup_video_script import VIDEO_SCRIPTS, all_scripts_count, get_video_script


# ── Agent teasers ────────────────────────────────────────────────────────────


def test_diagnostic_price_is_45000():
    assert DIAGNOSTIC_PRICE_RUB == 45_000


def test_three_teasers_built():
    layer_scores = {"01": 60, "02": 50, "03": 40, "04": 35}
    teasers = build_three_teasers(
        layer_scores,
        margin_pct=8.0,
        conv_pct=12.0,
        hours_per_week=55.0,
        segment_display="IT-агентство",
    )
    assert len(teasers) == 3
    agents = {t["agent"] for t in teasers}
    assert agents == {"analyst", "writer", "monitor"}


def test_each_teaser_has_required_fields():
    layer_scores = {"01": 70, "02": 50, "03": 40, "04": 60}
    teasers = build_three_teasers(
        layer_scores, margin_pct=10.0, conv_pct=8.0, hours_per_week=50.0,
        segment_display="онлайн-школа",
    )
    for t in teasers:
        assert "title" in t and t["title"]
        assert "body" in t and len(t["body"]) > 50
        assert "agent" in t
        assert "layer" in t and t["layer"] in {"01", "02", "03", "04"}


def test_analyst_targets_money_when_weak():
    """АНАЛИЗ-АГЕНТ показывается под Деньги если 04 ≤ 50."""
    scores = {"01": 80, "02": 80, "03": 80, "04": 30}
    t = analyst_agent_teaser(scores, margin_pct=5.0, segment_display="X")
    assert t["layer"] == "04"
    assert "Деньги" in t["title"] or "маржу" in t["body"]


def test_writer_targets_ops_when_weaker():
    scores = {"01": 80, "02": 70, "03": 40, "04": 80}
    t = writer_agent_teaser(scores, hours_per_week=55.0)
    assert t["layer"] == "03"


def test_monitor_targets_money_when_weaker():
    scores = {"01": 80, "02": 80, "03": 80, "04": 30}
    t = monitor_agent_teaser(scores, margin_pct=5.0, conv_pct=15.0)
    assert t["layer"] == "04"


# ── CTA block ────────────────────────────────────────────────────────────────


def test_diagnostic_cta_has_45k_price():
    cta = diagnostic_cta_block(score=50)
    assert cta["price_rub"] == 45_000
    assert "45 000" in cta["title"] or "45000" in cta["title"]
    assert "diagnostic_waitlist" in cta["deep_link"]
    assert len(cta["bullets"]) >= 4


def test_diagnostic_cta_categories_aligned():
    """category-color из same таблицы что в Mini."""
    assert diagnostic_cta_block(20)["category_color"] == "red"
    assert diagnostic_cta_block(50)["category_color"] == "orange"
    assert diagnostic_cta_block(70)["category_color"] == "yellow"
    assert diagnostic_cta_block(90)["category_color"] == "green"


# ── Video scripts ────────────────────────────────────────────────────────────


def test_all_24_canonical_scripts_present():
    """24 канонических + other = 28. ТЗ требует минимум 24 (6×4)."""
    assert all_scripts_count() >= 24


def test_each_segment_has_4_stages():
    expected_stages = {"start", "team", "structure", "maturity"}
    for segment, by_stage in VIDEO_SCRIPTS.items():
        assert set(by_stage.keys()) == expected_stages, (
            f"Segment {segment} missing stages: {expected_stages - set(by_stage.keys())}"
        )


def test_each_script_has_required_fields():
    for segment, by_stage in VIDEO_SCRIPTS.items():
        for stage, tmpl in by_stage.items():
            for field in ("intro", "focus", "layers", "next_step"):
                assert field in tmpl, f"{segment}/{stage} missing field: {field}"
            assert len(tmpl["layers"]) == 4, (
                f"{segment}/{stage} has {len(tmpl['layers'])} layer notes (expected 4)"
            )


def test_get_video_script_fallback():
    """Несуществующая комбинация → шаблон из 'other'."""
    script = get_video_script("nonexistent", "stage_x")
    assert "intro" in script
    assert "focus" in script
    assert len(script["layers"]) == 4


def test_no_old_diagnostic_price_in_scripts():
    """В шаблонах видео нет упоминания старой цены Диагностики (25 000)."""
    for segment, by_stage in VIDEO_SCRIPTS.items():
        for stage, tmpl in by_stage.items():
            full_text = tmpl["intro"] + tmpl["focus"] + " ".join(tmpl["layers"]) + tmpl["next_step"]
            assert "25 000" not in full_text, f"{segment}/{stage} contains old price 25 000"
            assert "25000" not in full_text, f"{segment}/{stage} contains old price 25000"
