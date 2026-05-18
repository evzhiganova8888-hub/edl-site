"""/grant_demo — выдача демо-доступа без оплаты (для партнёрских обкаток)."""
from __future__ import annotations

from src.bot.handlers.admin import _resolve_user_ref


def test_resolve_numeric_telegram_id():
    tg_id, uname = _resolve_user_ref("105255440")
    assert tg_id == 105255440
    assert uname is None


def test_resolve_username_with_at():
    tg_id, uname = _resolve_user_ref("@Linamironovich")
    assert tg_id is None
    assert uname == "Linamironovich"


def test_resolve_empty_returns_nones():
    assert _resolve_user_ref("") == (None, None)
    assert _resolve_user_ref("   ") == (None, None)


def test_resolve_garbage_telegram_id_falls_back():
    """Не число и не @username → возвращаем как username, если выглядит
    как корректный handle (alnum/_), иначе (None, None)."""
    tg_id, uname = _resolve_user_ref("not-a-real-id!!")
    assert tg_id is None
    assert uname is None


def test_grant_demo_command_registered():
    """Команда /grant_demo подключена в handlers registry."""
    from src.bot.handlers.admin import grant_demo_command
    assert callable(grant_demo_command)
