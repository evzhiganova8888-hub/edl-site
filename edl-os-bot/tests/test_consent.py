"""Согласие на ПД — текст, хэш версии политики, статус юзера."""
from src.core.consent import consent_text, has_consent, policy_hash


def test_policy_hash_stable():
    assert policy_hash() == policy_hash()
    assert len(policy_hash()) == 16


def test_consent_text_mentions_law_and_ip():
    text = consent_text()
    assert "152-ФЗ" not in text  # текст не цитирует номер закона, чтоб не казённо
    assert "ИП Жиганова" in text
    assert "027507994838" in text


def test_consent_text_has_policy_url():
    assert "elephantdreams" in consent_text()


def test_has_consent_false_by_default():
    class Stub:
        consent_pd_given_at = None

    assert has_consent(Stub()) is False
