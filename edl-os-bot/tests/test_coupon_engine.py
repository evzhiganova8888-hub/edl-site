"""Юнит-тесты coupon_engine — главный инвариант: 24h TTL.

Что проверяем:
1. `_generate_code` — формат и уникальность через nonce.
2. `_hours_left` — корректно считает остаток / 0 / отрицательное обнуляется.
3. `view_of` — флипает status='active' → 'expired' если время прошло,
   даже если в БД ещё active. Это гарантия времени поверх БД.
4. Интеграция issue → activate → mark_used через моки AsyncSession,
   с пристальной проверкой что expired-купоны не могут быть use'аны.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core import coupon_engine as ce


# ── Pure-function tests ──────────────────────────────────────────────────────


def test_default_ttl_is_24_hours():
    """Жёсткое требование 21.05.2026: купон действует ровно 24 часа."""
    assert ce.DEFAULT_TTL == timedelta(hours=24)


def test_default_pricing_consistent():
    expected_discounted = int(
        ce.DEFAULT_ORIGINAL_PRICE_RUB * (100 - ce.DEFAULT_DISCOUNT_PCT) / 100
    )
    assert ce.DEFAULT_DISCOUNTED_PRICE_RUB == expected_discounted


def test_generate_code_format():
    code = ce._generate_code(user_id=12345)
    parts = code.split("-")
    assert parts[0] == ce.CODE_PREFIX == "EDLPLUS"
    assert parts[1] == "12345"
    # 4 hex символа nonce
    assert len(parts[2]) == 4
    assert all(c in "0123456789ABCDEF" for c in parts[2])


def test_generate_code_changes_each_call():
    """Nonce должен различаться (вероятность коллизии ≈ 1/65536)."""
    codes = {ce._generate_code(user_id=7) for _ in range(20)}
    assert len(codes) > 1  # не все одинаковые


def test_hours_left_positive():
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    expires_at = now + timedelta(hours=5, minutes=30)
    assert ce._hours_left(expires_at, now=now) == 5


def test_hours_left_zero_if_expired():
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    expires_at = now - timedelta(hours=1)
    assert ce._hours_left(expires_at, now=now) == 0


def test_hours_left_at_exact_expiry():
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    # ровно в момент истечения — не активен (см. view_of contract)
    assert ce._hours_left(now, now=now) == 0


# ── view_of: проверка инварианта «время побеждает БД» ────────────────────────


def _make_coupon(*, status: str, expires_at: datetime, **extra) -> MagicMock:
    coupon = MagicMock()
    coupon.code = extra.get("code", "EDLPLUS-1-ABCD")
    coupon.status = status
    coupon.expires_at = expires_at
    coupon.discounted_price_rub = ce.DEFAULT_DISCOUNTED_PRICE_RUB
    coupon.original_price_rub = ce.DEFAULT_ORIGINAL_PRICE_RUB
    coupon.discount_pct = ce.DEFAULT_DISCOUNT_PCT
    coupon.user_id = extra.get("user_id", 1)
    coupon.issued_at = expires_at - ce.DEFAULT_TTL
    coupon.id = uuid4()
    return coupon


def test_view_of_active_in_window():
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    coupon = _make_coupon(status="active", expires_at=now + timedelta(hours=10))
    view = ce.view_of(coupon, now=now)
    assert view.status == "active"
    assert view.hours_left == 10


def test_view_of_active_in_db_but_expired_in_time():
    """Ключевой инвариант: если БД говорит 'active' но время прошло —
    клиент видит 'expired' и hours_left=0. Защищает от окна гонки между
    истечением и celery-task expire_overdue.
    """
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    coupon = _make_coupon(
        status="active", expires_at=now - timedelta(minutes=5)
    )
    view = ce.view_of(coupon, now=now)
    assert view.status == "expired"
    assert view.hours_left == 0


def test_view_of_used():
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    coupon = _make_coupon(status="used", expires_at=now + timedelta(hours=10))
    view = ce.view_of(coupon, now=now)
    assert view.status == "used"


def test_view_of_none_returns_not_found():
    view = ce.view_of(None)
    assert view.status == "not_found"
    assert view.code == ""


# ── Engine flow tests (через моки AsyncSession) ──────────────────────────────


def _make_session(initial_rows: list | None = None):
    """Минимальный мок AsyncSession для coupon_engine.

    Поддерживает chain `select(Coupon).where(...).where(...)`:
    .execute(stmt) → result.scalar_one_or_none() / scalars().first() /
    scalars().all() читают из подложки.
    """
    session = AsyncMock()
    rows = list(initial_rows or [])
    state = {"rows": rows}

    async def execute(stmt):
        result = MagicMock()
        # Простой stub: всегда возвращает текущий снэпшот rows.
        # Тесты могут проверять конкретный путь через side_effects.
        scalars = MagicMock()
        scalars.first.return_value = state["rows"][0] if state["rows"] else None
        scalars.all.return_value = list(state["rows"])
        result.scalars.return_value = scalars
        result.scalar_one_or_none.return_value = (
            state["rows"][0] if state["rows"] else None
        )
        return result

    session.execute = execute

    def add(obj):
        state["rows"].append(obj)

    session.add = add
    session.flush = AsyncMock()
    return session, state


@pytest.mark.asyncio
async def test_get_active_coupon_expires_if_time_passed():
    """Активный по БД, но время прошло → возвращает None и flush'ит expired."""
    now = ce._now()
    coupon = _make_coupon(
        status="active", expires_at=now - timedelta(seconds=1)
    )
    session, _ = _make_session([coupon])

    result = await ce.get_active_coupon_for_user(session, user_id=1)
    assert result is None
    assert coupon.status == "expired"
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_get_active_coupon_returns_alive():
    now = ce._now()
    coupon = _make_coupon(
        status="active", expires_at=now + timedelta(hours=5)
    )
    session, _ = _make_session([coupon])

    result = await ce.get_active_coupon_for_user(session, user_id=1)
    assert result is coupon
    assert coupon.status == "active"


@pytest.mark.asyncio
async def test_mark_coupon_used_rejects_expired_by_time():
    """Купон в БД ещё 'active', но время прошло → mark_used должен отказать."""
    now = ce._now()
    coupon = _make_coupon(
        status="active", expires_at=now - timedelta(seconds=1)
    )
    session, _ = _make_session([coupon])

    ok = await ce.mark_coupon_used(session, code=coupon.code)
    assert ok is False
    assert coupon.status == "expired"


@pytest.mark.asyncio
async def test_mark_coupon_used_succeeds_when_active():
    now = ce._now()
    coupon = _make_coupon(
        status="active", expires_at=now + timedelta(hours=1)
    )
    session, _ = _make_session([coupon])

    ok = await ce.mark_coupon_used(session, code=coupon.code)
    assert ok is True
    assert coupon.status == "used"
    assert coupon.used_at is not None


@pytest.mark.asyncio
async def test_mark_coupon_used_rejects_double_use():
    now = ce._now()
    coupon = _make_coupon(
        status="used", expires_at=now + timedelta(hours=1)
    )
    coupon.used_at = now
    session, _ = _make_session([coupon])

    ok = await ce.mark_coupon_used(session, code=coupon.code)
    assert ok is False


@pytest.mark.asyncio
async def test_activate_coupon_wrong_user_returns_not_found():
    now = ce._now()
    coupon = _make_coupon(
        status="active", expires_at=now + timedelta(hours=1), user_id=42
    )
    session, _ = _make_session([coupon])

    view = await ce.activate_coupon(session, code=coupon.code, user_id=99)
    assert view.status == "not_found"


@pytest.mark.asyncio
async def test_issue_coupon_validates_ttl():
    session, _ = _make_session([])
    with pytest.raises(ValueError):
        await ce.issue_coupon(session, user_id=1, ttl=timedelta(0))


@pytest.mark.asyncio
async def test_issue_coupon_validates_discount():
    session, _ = _make_session([])
    with pytest.raises(ValueError):
        await ce.issue_coupon(session, user_id=1, discount_pct=0)
    with pytest.raises(ValueError):
        await ce.issue_coupon(session, user_id=1, discount_pct=100)
