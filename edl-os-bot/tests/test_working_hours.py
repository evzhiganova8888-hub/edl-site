"""Тесты рабочих часов и hand-off формулировок."""
from datetime import datetime
from zoneinfo import ZoneInfo

from src.core.working_hours import (
    humanize_window,
    is_working_now,
    next_business_window,
    now_msk,
)

MSK = ZoneInfo("Europe/Moscow")


def test_wednesday_noon_is_working():
    wed_noon = datetime(2026, 5, 13, 12, 0, tzinfo=MSK)  # среда
    assert is_working_now(wed_noon) is True


def test_saturday_noon_is_not_working():
    sat = datetime(2026, 5, 16, 12, 0, tzinfo=MSK)
    assert is_working_now(sat) is False


def test_wednesday_evening_not_working():
    wed_evening = datetime(2026, 5, 13, 20, 0, tzinfo=MSK)
    assert is_working_now(wed_evening) is False


def test_next_window_from_saturday_morning():
    sat = datetime(2026, 5, 16, 9, 0, tzinfo=MSK)
    nxt = next_business_window(sat)
    assert nxt.weekday() == 0  # понедельник
    assert nxt.hour == 10


def test_humanize_returns_string():
    out = humanize_window(next_business_window(now_msk()))
    assert "МСК" in out
    assert ":" in out
