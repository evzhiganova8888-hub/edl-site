"""PD sanitizer — гарантия что в LLM не уходит email/телефон/ИНН/карта."""
from src.core.pd_sanitize import contains_pd, sanitize


def test_email_removed():
    assert "ivanov@example.com" not in sanitize("пишите на ivanov@example.com")


def test_phone_removed():
    s = sanitize("звоните +7 (912) 345-67-89")
    assert "912" not in s


def test_inn_removed():
    assert "0275079948" not in sanitize("ИНН 0275079948")


def test_card_removed():
    s = sanitize("карта 1234 5678 9012 3456")
    assert "1234 5678" not in s


def test_tg_username_removed():
    assert "@lvanKhudyakov" not in sanitize("напишите @lvanKhudyakov")


def test_contains_pd_true():
    assert contains_pd("моя почта user@x.ru")


def test_contains_pd_false():
    assert not contains_pd("у нас 22 сотрудника в производстве")


def test_empty_input():
    assert sanitize("") == ""
    assert sanitize(None) is None  # type: ignore[arg-type]
