"""F7: Pause/Resume Чекапа — тесты хелперов."""
from __future__ import annotations

import pytest
from src.bot.handlers.checkup import is_in_checkup_fsm


def test_is_in_checkup_fsm_true():
    user_data = {"checkup_state": "await_answer", "checkup_app_id": "some-uuid"}
    assert is_in_checkup_fsm(user_data) is True


def test_is_in_checkup_fsm_false_empty():
    assert is_in_checkup_fsm({}) is False


def test_is_in_checkup_fsm_false_no_app():
    assert is_in_checkup_fsm({"checkup_state": "await_answer"}) is False


def test_is_in_checkup_fsm_false_no_state():
    assert is_in_checkup_fsm({"checkup_app_id": "some-uuid"}) is False


@pytest.mark.asyncio
async def test_get_paused_checkup_returns_none_for_unknown_user(monkeypatch):
    """Нет записи → возвращает None без исключений."""
    from unittest.mock import AsyncMock, MagicMock

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    from src.db.repos import get_or_create_user
    mock_user = MagicMock()
    mock_user.id = 999

    import src.bot.handlers.checkup as checkup_module
    monkeypatch.setattr(checkup_module, "async_session_factory", lambda: mock_factory)
    monkeypatch.setattr(
        "src.bot.handlers.checkup.get_or_create_user",
        AsyncMock(return_value=(mock_user, False)),
    )

    result = await checkup_module.get_paused_checkup(telegram_id=12345)
    assert result is None
