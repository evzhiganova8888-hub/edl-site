"""Working hours logic — out-of-hours hand-off (§12 ТЗ + §13 v3.1).

Окно 10:00–19:00 МСК Пн–Пт, исключая официальные нерабочие праздничные
дни РФ. Для out-of-hours формулировок бот выдаёт конкретный ближайший
час начала рабочего окна, не абстрактное «скоро».
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.core.config import settings

_WEEKDAYS_RU = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]

# Официальные нерабочие праздничные дни РФ на ближайшие годы (ст. 112 ТК).
# Перенос выходных с производственного календаря РФ — добавляется по факту
# постановлений Правительства. Базовый список безопасен на «не работаем».
RF_HOLIDAYS: set[date] = {
    # 2026
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6),
    date(2026, 1, 7), date(2026, 1, 8),
    date(2026, 2, 23),
    date(2026, 3, 9),  # перенос с 8 марта (вс)
    date(2026, 5, 1), date(2026, 5, 4), date(2026, 5, 5),  # перенос с 5 янв.
    date(2026, 5, 11),  # перенос с 9 мая (сб)
    date(2026, 6, 12),
    date(2026, 11, 4),
    # 2027 — базовые федеральные, без переноса
    date(2027, 1, 1), date(2027, 1, 4), date(2027, 1, 5),
    date(2027, 1, 6), date(2027, 1, 7), date(2027, 1, 8),
    date(2027, 2, 23),
    date(2027, 3, 8),
    date(2027, 5, 3),  # перенос с 1 мая (сб)
    date(2027, 5, 10),  # перенос с 9 мая (вс)
    date(2027, 6, 14),  # перенос с 12 июня (сб)
    date(2027, 11, 4),
}


def now_msk() -> datetime:
    return datetime.now(tz=ZoneInfo(settings.timezone))


def is_holiday(d: date) -> bool:
    return d in RF_HOLIDAYS


def is_working_day(d: date) -> bool:
    """Будний (Пн–Пт) и не праздник."""
    return d.weekday() < 5 and not is_holiday(d)


def is_working_now(now: datetime | None = None) -> bool:
    now = now or now_msk()
    if not is_working_day(now.date()):
        return False
    open_t = time(settings.working_hours_start, 0)
    close_t = time(settings.working_hours_end, 0)
    return open_t <= now.time() < close_t


def next_business_window(now: datetime | None = None) -> datetime:
    """Ближайший момент начала рабочего окна (10:00 МСК) с учётом праздников."""
    now = now or now_msk()
    candidate = now.replace(
        hour=settings.working_hours_start, minute=0, second=0, microsecond=0
    )
    if now.time() >= time(settings.working_hours_end, 0):
        candidate = candidate + timedelta(days=1)
    elif now.time() < time(settings.working_hours_start, 0):
        pass
    else:
        # уже в рабочем окне И сегодня рабочий день
        if is_working_day(now.date()):
            return now
        # сегодня выходной/праздник, но время в окне — сдвигаем на следующий рабочий
        candidate = candidate + timedelta(days=1)
    while not is_working_day(candidate.date()):
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
