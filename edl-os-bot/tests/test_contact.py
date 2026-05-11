"""Валидация контактных полей."""
from src.core.contact import (
    normalize_company,
    normalize_email,
    normalize_full_name,
    normalize_phone,
)


def test_email_lowercase():
    assert normalize_email("USER@Example.COM") == "user@example.com"


def test_email_invalid():
    assert normalize_email("not-an-email") is None
    assert normalize_email("@x.ru") is None
    assert normalize_email("user@") is None


def test_phone_normalizes_8_to_plus7():
    assert normalize_phone("8 912 345-67-89") == "+79123456789"


def test_phone_plus7():
    assert normalize_phone("+7 (912) 345 67 89") == "+79123456789"


def test_phone_invalid():
    assert normalize_phone("123") is None
    assert normalize_phone("abc") is None


def test_full_name_ok():
    assert normalize_full_name("Иванов Иван") == "Иванов Иван"
    assert normalize_full_name("Иванов  Иван   Сергеевич") == "Иванов Иван Сергеевич"


def test_full_name_single_word_invalid():
    assert normalize_full_name("Иванов") is None
    assert normalize_full_name("") is None


def test_company_min_length():
    assert normalize_company("Я") is None
    assert normalize_company("ИП Жиганова") == "ИП Жиганова"
