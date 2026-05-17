"""Оферта: hash версии, текст содержит ключевые гарантии."""
from src.core.offer import OFFER_VERSION, offer_hash, offer_summary


def test_offer_hash_stable():
    assert offer_hash() == offer_hash()
    assert len(offer_hash()) == 16


def test_offer_summary_mentions_guarantee():
    s = offer_summary()
    assert "100%" in s
    assert "14 календарных дней" in s   # Точная фраза из offer_summary()
    assert "ИП Жиганова" in s
    assert "027507994838" in s
    # В stub/manual режиме — ручная оплата, не Robokassa
    assert "Robokassa" not in s


def test_offer_version_is_dated():
    assert "2026" in OFFER_VERSION
