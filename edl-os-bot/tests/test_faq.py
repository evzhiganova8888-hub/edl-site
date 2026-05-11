"""FAQ rules-based: загрузка + поиск по ключевым словам."""
from src.core import faq


def test_load_11_items():
    items = faq.all_items()
    assert len(items) == 11


def test_get_by_index_1_based():
    item = faq.get_by_index(1)
    assert item is not None
    assert "Чекап" in item.question or "чекап" in item.question.lower()


def test_get_by_index_out_of_range():
    assert faq.get_by_index(0) is None
    assert faq.get_by_index(99) is None


def test_search_vat():
    item = faq.search("ндс 2026")
    assert item is not None
    assert "ндс" in item.question.lower() or "ндс" in item.answer.lower()


def test_search_guarantee():
    item = faq.search("какие у вас гарантии возврата?")
    assert item is not None
    assert "гарантии" in item.question.lower() or "Возврат" in item.answer


def test_search_no_match():
    assert faq.search("погода в Москве") is None


def test_search_empty():
    assert faq.search("") is None
