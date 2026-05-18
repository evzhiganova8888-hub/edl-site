"""B1 fix (19.05.2026): после accept consent purchase FSM возобновляется.

Прежде: клик «Купить Plus» без consent → consent-форма → accept → main_menu.
FSM-ключи никогда не выставлялись и Application не создавалась. Юзер видел
«Спасибо, согласие зафиксировано» и тишину.

Теперь: start_purchase запоминает intent в context.user_data, accept consent
вызывает _begin_purchase, который создаёт Application и спрашивает ФИО.
"""
from __future__ import annotations

import pytest

from src.bot.handlers import audit, consent


def test_pending_post_consent_key_exists():
    """Контракт между audit и consent: ключ присутствует."""
    assert audit.PENDING_POST_CONSENT_KEY == "pending_post_consent"


def test_begin_purchase_is_callable():
    """consent.handle_consent импортирует audit._begin_purchase — должно
    существовать, иначе resume сломан."""
    assert callable(audit._begin_purchase)


def test_consent_handler_imports_audit_lazily():
    """Импорт audit внутри handle_consent (не на top-level) — защита от
    циклической зависимости consent ↔ audit."""
    import inspect
    src = inspect.getsource(consent.handle_consent)
    # Lazy import — иначе при загрузке модуля consent падает с ImportError.
    assert "from src.bot.handlers import audit" in src
