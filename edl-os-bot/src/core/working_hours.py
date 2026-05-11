"""Working hours logic — out-of-hours hand-off (§12 ТЗ).

Окно 10:00–19:00 МСК Пн–Пт. Для out-of-hours формулировок бот выдаёт
конкретный ближайший час начала рабочего окна, а не абстрактные слова.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.core.config import settings

_WEEKDAYS_RU = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]


def now_msk() -> datetime:
    return datetime.now(tz=ZoneInfo(settings.timezone))


def is_working_now(now: datetime | None = None) -> bool:
    now = now or now_msk()
    if now.weekday() >= 5:  # Sat/Sun
        return False
    open_t = time(settings.working_hours_start, 0)
    close_t = time(settings.working_hours_end, 0)
    return open_t <= now.time() < close_t


def next_business_window(now: datetime | None = None) -> datetime:
    """Ближайший момент начала рабочего окна (10:00 МСК)."""
    now = now or now_msk()
    candidate = now.replace(
        hour=settings.working_hours_start, minute=0, second=0, microsecond=0
    )
    if now.time() >= time(settings.working_hours_end, 0):
        candidate = candidate + timedelta(days=1)
    elif now.time() < time(settings.working_hours_start, 0):
        pass
    else:
        # уже в рабочем окне
        return now
    while candidate.weekday() >= 5:
        candidate = candidate + timedelta(days=1)
    return candidate


def humanize_window(dt: datetime) -> str:
    """«в понедельник в 10:00 МСК» или «сегодня в 14:00 МСК»."""
    now = now_msk()
    if dt.date() == now.date():
        prefix = "сегодня"
    elif dt.date() == (now + timedelta(days=1)).date():
        prefix = "завтра"
    else:
        prefix = f"в {_WEEKDAYS_RU[dt.weekday()]}"
    return f"{prefix} в {dt.strftime('%H:%M')} МСК"
