"""Промокоды на Диагностику с жёстким 24-часовым TTL.

Контракт времени (главный инвариант, требование пользователя 21.05.2026):

- `issued_at` = момент выдачи купона (UTC, server time).
- `expires_at` = `issued_at + DEFAULT_TTL` (= 24 часа по умолчанию).
- Купон считается активным только если ОБА выполнены:
    1. `status == 'active'`;
    2. `datetime.now(UTC) <= expires_at`.

Двойная проверка нужна потому, что между моментом фактического истечения
по времени и моментом запуска celery-task `expire_coupons` существует
окно, в которое статус всё ещё `'active'`. Все клиентские пути
(activate_coupon, /diagnostika) проверяют время явно, не доверяя только
колонке `status`.

Купон одноразовый. После activate он остаётся `'active'` до подтверждения
оплаты Иваном (`mark_coupon_used`), потому что между обращением клиента
и выставлением счёта может пройти несколько часов. Если 24 часа истекли
до подтверждения оплаты — купон автоматически становится `'expired'`
(время побеждает).
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Coupon, CouponUsage

logger = logging.getLogger(__name__)

# ── Конфигурация (закреплено ТЗ §8 и явным требованием 21.05.2026) ───────────
DEFAULT_TTL = timedelta(hours=24)
DEFAULT_DISCOUNT_PCT = 20
DEFAULT_ORIGINAL_PRICE_RUB = 45_000
DEFAULT_DISCOUNTED_PRICE_RUB = 36_000  # 45 000 × (1 − 0.20)
DEFAULT_TARGET_PRODUCT = "diagnostika"
CODE_PREFIX = "EDLPLUS"


# ── Результаты операций ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class CouponView:
    """Snapshot для сообщений пользователю — без секретов и внутренних UUID."""

    code: str
    status: str  # 'active' | 'used' | 'expired' | 'not_found'
    expires_at: datetime | None
    discounted_price_rub: int
    original_price_rub: int
    discount_pct: int
    hours_left: int | None  # для отображения, None если уже истёк


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hours_left(expires_at: datetime, now: datetime | None = None) -> int:
    """Сколько целых часов осталось до истечения. 0 если уже прошло."""
    now = now or _now()
    if expires_at <= now:
        return 0
    return max(0, int((expires_at - now).total_seconds() // 3600))


def _generate_code(user_id: int) -> str:
    """`EDLPLUS-{user_id}-{NONCE4}`. Уникальность гарантируется проверкой в БД."""
    nonce = secrets.token_hex(2).upper()  # 4 hex символа, ~65k значений
    return f"{CODE_PREFIX}-{user_id}-{nonce}"


# ── Issue ─────────────────────────────────────────────────────────────────────


async def issue_coupon(
    session: AsyncSession,
    *,
    user_id: int,
    application_id: UUID | None = None,
    ttl: timedelta = DEFAULT_TTL,
    discount_pct: int = DEFAULT_DISCOUNT_PCT,
    original_price_rub: int = DEFAULT_ORIGINAL_PRICE_RUB,
    target_product: str = DEFAULT_TARGET_PRODUCT,
) -> Coupon:
    """Выдать новый купон.

    Idempotency: если у `user_id` уже есть `active` купон на тот же
    `target_product` — возвращаем существующий (не создаём дубликат).

    Если у предыдущих купонов время истекло, но статус всё ещё `'active'`
    (celery ещё не отработал) — отмечаем их `'expired'` синхронно перед
    выдачей нового. Это защищает инвариант «один активный купон на
    user × product».
    """
    if ttl <= timedelta(0):
        raise ValueError("ttl must be positive")
    if not 0 < discount_pct < 100:
        raise ValueError("discount_pct must be between 1 and 99")

    now = _now()
    # 1) Подметаем истёкшие active-купоны этого user × product
    stmt = (
        select(Coupon)
        .where(Coupon.user_id == user_id)
        .where(Coupon.target_product == target_product)
        .where(Coupon.status == "active")
    )
    rows = (await session.execute(stmt)).scalars().all()
    existing_active: Coupon | None = None
    for row in rows:
        if row.expires_at <= now:
            row.status = "expired"
        else:
            existing_active = row

    if existing_active is not None:
        # Idempotent: уже есть живой купон
        return existing_active

    # 2) Генерируем уникальный code (на практике коллизии не будет, но
    # перестрахуемся ретраем)
    code: str | None = None
    for _ in range(5):
        candidate = _generate_code(user_id)
        clash = (
            await session.execute(select(Coupon).where(Coupon.code == candidate))
        ).scalar_one_or_none()
        if clash is None:
            code = candidate
            break
    if code is None:
        raise RuntimeError("could not generate unique coupon code after 5 attempts")

    discounted = int(round(original_price_rub * (100 - discount_pct) / 100))
    coupon = Coupon(
        code=code,
        user_id=user_id,
        application_id=application_id,
        target_product=target_product,
        discount_pct=discount_pct,
        original_price_rub=original_price_rub,
        discounted_price_rub=discounted,
        issued_at=now,
        expires_at=now + ttl,
        status="active",
    )
    session.add(coupon)
    await session.flush()
    logger.info(
        "coupon.issued code=%s user_id=%s ttl_hours=%s expires_at=%s",
        code,
        user_id,
        ttl.total_seconds() // 3600,
        coupon.expires_at.isoformat(),
    )
    return coupon


# ── Lookup / activation ──────────────────────────────────────────────────────


async def get_coupon_by_code(session: AsyncSession, code: str) -> Coupon | None:
    return (
        await session.execute(select(Coupon).where(Coupon.code == code))
    ).scalar_one_or_none()


async def get_active_coupon_for_user(
    session: AsyncSession, user_id: int, target_product: str = DEFAULT_TARGET_PRODUCT
) -> Coupon | None:
    """Активный купон для пользователя или None.

    Гарантия времени: даже если в БД status='active', но время вышло —
    возвращаем None и синхронно помечаем купон 'expired'.
    """
    stmt = (
        select(Coupon)
        .where(Coupon.user_id == user_id)
        .where(Coupon.target_product == target_product)
        .where(Coupon.status == "active")
        .order_by(Coupon.issued_at.desc())
    )
    row = (await session.execute(stmt)).scalars().first()
    if row is None:
        return None
    if row.expires_at <= _now():
        row.status = "expired"
        await session.flush()
        return None
    return row


def view_of(coupon: Coupon | None, now: datetime | None = None) -> CouponView:
    """Сериализация для текстов бота."""
    if coupon is None:
        return CouponView(
            code="",
            status="not_found",
            expires_at=None,
            discounted_price_rub=0,
            original_price_rub=0,
            discount_pct=0,
            hours_left=None,
        )
    now = now or _now()
    actual_status = coupon.status
    if actual_status == "active" and coupon.expires_at <= now:
        actual_status = "expired"
    return CouponView(
        code=coupon.code,
        status=actual_status,
        expires_at=coupon.expires_at,
        discounted_price_rub=coupon.discounted_price_rub,
        original_price_rub=coupon.original_price_rub,
        discount_pct=coupon.discount_pct,
        hours_left=_hours_left(coupon.expires_at, now=now) if actual_status == "active" else 0,
    )


async def activate_coupon(
    session: AsyncSession, *, code: str, user_id: int
) -> CouponView:
    """Клиент жмёт /diagnostika с кодом → проверяем валидность.

    Не помечает used: используется только `mark_coupon_used` после
    подтверждения оплаты Иваном. Возвращает view с актуальным статусом.
    """
    coupon = await get_coupon_by_code(session, code)
    if coupon is None or coupon.user_id != user_id:
        return view_of(None)

    now = _now()
    # Жёсткое истечение по времени независимо от status в БД
    if coupon.status == "active" and coupon.expires_at <= now:
        coupon.status = "expired"
        await session.flush()

    return view_of(coupon, now=now)


async def mark_coupon_used(
    session: AsyncSession,
    *,
    code: str,
    activated_via: str = "ivan_manual",
    diagnostika_application_id: UUID | None = None,
) -> bool:
    """Иван подтвердил оплату Диагностики с этим купоном.

    Возвращает False если купон уже use'ан, истёк, не найден или его
    нельзя использовать. После успеха записывает CouponUsage для аудита.
    """
    coupon = await get_coupon_by_code(session, code)
    if coupon is None:
        return False
    now = _now()
    if coupon.expires_at <= now and coupon.status == "active":
        # Истёк по времени между активацией и подтверждением — время побеждает
        coupon.status = "expired"
        await session.flush()
        return False
    if coupon.status != "active":
        return False

    coupon.status = "used"
    coupon.used_at = now
    session.add(
        CouponUsage(
            coupon_id=coupon.id,
            used_at=now,
            activated_via=activated_via,
            diagnostika_application_id=diagnostika_application_id,
        )
    )
    await session.flush()
    logger.info("coupon.used code=%s via=%s", code, activated_via)
    return True


async def expire_overdue_coupons(session: AsyncSession) -> int:
    """Celery-task helper: пометить все просроченные active-купоны 'expired'.

    Не критичен для корректности — все клиентские пути делают двойную
    проверку. Полезен для аналитики и чтобы /status показывал актуальный
    статус без дополнительных запросов.

    Возвращает число помеченных записей.
    """
    now = _now()
    stmt = (
        select(Coupon)
        .where(Coupon.status == "active")
        .where(Coupon.expires_at <= now)
    )
    rows = (await session.execute(stmt)).scalars().all()
    for row in rows:
        row.status = "expired"
    await session.flush()
    if rows:
        logger.info("coupon.expire_overdue n=%d", len(rows))
    return len(rows)
