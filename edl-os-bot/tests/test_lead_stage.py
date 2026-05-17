"""F6: Тесты для lead_stage.py — логика переходов между стадиями."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.lead_stage import LEAD_STAGES, calculate_lead_stage


def _make_user(stage: str = "cold", lead_stage: str | None = None, lead_stage_updated_at=None):
    user = MagicMock()
    user.id = 1
    user.stage = stage
    user.lead_stage = lead_stage or stage
    user.lead_stage_updated_at = lead_stage_updated_at
    return user


def _make_session(paid_app=None, hot_event=None, warm_event=None):
    """Мок AsyncSession с заданными результатами SELECT."""
    session = AsyncMock()

    async def execute(stmt):
        result = MagicMock()
        # Определяем по порядку вызовов: 1=paid, 2=hot, 3=warm
        if not hasattr(execute, "_calls"):
            execute._calls = 0
        execute._calls += 1
        if execute._calls == 1:
            result.scalar_one_or_none.return_value = paid_app
        elif execute._calls == 2:
            result.scalar_one_or_none.return_value = hot_event
        else:
            result.scalar_one_or_none.return_value = warm_event
        return result

    session.execute = execute
    return session


@pytest.mark.asyncio
async def test_cold_no_events():
    user = _make_user("cold")
    session = _make_session()
    stage = await calculate_lead_stage(user, session)
    assert stage == "cold"


@pytest.mark.asyncio
async def test_warm_after_quiz_completed():
    user = _make_user("cold")
    warm_event = MagicMock()
    session = _make_session(warm_event=warm_event)
    stage = await calculate_lead_stage(user, session)
    assert stage == "warm"


@pytest.mark.asyncio
async def test_hot_after_purchase_started():
    user = _make_user("warm")
    hot_event = MagicMock()
    session = _make_session(hot_event=hot_event)
    stage = await calculate_lead_stage(user, session)
    assert stage == "hot"


@pytest.mark.asyncio
async def test_client_after_payment():
    user = _make_user("hot")
    paid_app = MagicMock()
    session = _make_session(paid_app=paid_app)
    stage = await calculate_lead_stage(user, session)
    assert stage == "client"


@pytest.mark.asyncio
async def test_hot_cooldown_returns_warm():
    from datetime import datetime, timedelta, timezone
    user = _make_user("hot")
    user.lead_stage = "hot"
    user.lead_stage_updated_at = datetime.now(timezone.utc) - timedelta(days=8)
    hot_event = MagicMock()
    session = _make_session(hot_event=hot_event)
    stage = await calculate_lead_stage(user, session)
    assert stage == "warm"


def test_lead_stages_order():
    assert LEAD_STAGES == ["cold", "warm", "hot", "client"]
