"""Unit-тесты сегментации (§2 ТЗ)."""
from src.core.segment import (
    SEGMENTS,
    detect,
    detect_from_deep_link,
    detect_from_text,
    detect_sub_profile,
)


def test_all_segments_have_labels():
    from src.core.segment import SEGMENT_LABELS

    assert set(SEGMENT_LABELS.keys()) == set(SEGMENTS)


def test_deep_link_audit_services_legal():
    assert detect_from_deep_link("audit_services_legal") == "services_legal"


def test_deep_link_manufacturing_warm():
    assert detect_from_deep_link("manufacturing_warm") == "manufacturing"


def test_deep_link_unknown():
    assert detect_from_deep_link("totally_unknown") is None


def test_marker_words_manufacturing():
    assert detect_from_text("у нас цех мебельный, 22 человека") == "manufacturing"


def test_marker_words_b2b_saas():
    assert detect_from_text("vertical SaaS для агентств, MRR $30k") == "b2b_saas"


def test_sub_profile_consolidation_risk():
    assert detect_sub_profile("manufacturing", "у меня дробление, несколько ИП") == "consolidation_risk"


def test_sub_profile_unknown_segment():
    assert detect_sub_profile("nonexistent", "хоть что") is None


def test_full_detection_deep_link_wins():
    r = detect(payload="services_legal", text="что-то про производство")
    assert r.segment == "services_legal"
    assert r.method == "deep_link"


def test_full_detection_fallback():
    r = detect(payload=None, text="привет")
    assert r.segment == "other"
    assert r.method == "fallback"
