"""Rate limits per Telegram user (§C.4 ТЗ v3.1).

Защита от:
- спама / DDoS бота (стоимость LLM-токенов)
- цикличных оплат (двойные платежи)
- повторных refund-запросов
- token-флуда (50k токенов/день — мягкий потолок)

Хранилище — Redis (sliding window через ZSET). При недоступности Redis
лимиты деградируют в no-op и пишут warning, чтобы не блокировать пользователя
из-за инфраструктуры.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from src.core.config import settings

logger = logging.getLogger(__name__)

# Лимиты из §C.4 v3.1. Можно тюнить без передеплоя через env позже.
RATE_LIMITS = {
    "messages_per_minute": 10,
    "messages_per_hour": 100,
    "llm_tokens_per_day": 50_000,
    "payment_attempts_per_hour": 3,
    "refund_requests_per_lifetime": 1,
}

_client = None  # ленивый redis-клиент


def _get_redis():
    global _client
    if _client is not None:
        return _client
    try:
        import redis.asyncio as redis  # type: ignore

        _client = redis.from_url(settings.redis_url, decode_responses=True)
        return _client
    except Exception as e:
        logger.warning("Redis not available for rate limits: %s", e)
        _client = False
        return None


@dataclass
class LimitDecision:
    allowed: bool
    name: str
    used: int
    limit: int
    retry_after_seconds: int | None = None


async def _check_sliding_window(
    *,
    key: str,
    window_seconds: int,
    limit: int,
    increment: int = 1,
    fail_open: bool = True,
) -> LimitDecision:
    """ZSET sliding window: атомарно через pipeline.

    `fail_open=True` (по умолчанию) — при недоступности Redis пропускаем
    запрос. Используется для message-rate (нельзя блокировать пользователя
    из-за инфра-проблем).
    `fail_open=False` — при недоступности Redis запрос блокируется. Нужно
    для payment-rate (двойная оплата дороже временного отказа).

    Race-safe: zremrangebyscore + zcard + zadd выполняются в одном pipeline,
    без межтранзакционных окон.
    """
    r = _get_redis()
    if not r:
        return LimitDecision(allowed=fail_open, name=key, used=0, limit=limit)

    try:
        now = time.time()
        cutoff = now - window_seconds
        # uniqueness гарантируем через uuid-подобный suffix вместо коллизий на ms
        import uuid as _uuid
        member = f"{now}:{_uuid.uuid4().hex[:8]}"

        # Атомарный pipeline: чистка → добавление → подсчёт.
        # Если limit пробит — откатываем добавление через zrem.
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds + 10)
        _, _, used, _ = await pipe.execute()

        if used > limit:
            await r.zrem(key, member)
            oldest = await r.zrange(key, 0, 0, withscores=True)
            retry = None
            if oldest:
                retry = max(1, int(oldest[0][1] + window_seconds - now))
            return LimitDecision(
                allowed=False,
                name=key,
                used=used - 1,
                limit=limit,
                retry_after_seconds=retry,
            )
        return LimitDecision(allowed=True, name=key, used=used, limit=limit)
    except Exception as e:
        logger.warning(
            "Rate limit Redis error (%s) on %s — %s",
            e,
            key,
            "allowing" if fail_open else "BLOCKING (fail-closed)",
        )
        return LimitDecision(allowed=fail_open, name=key, used=0, limit=limit)


async def check_message(telegram_id: int) -> LimitDecision:
    """Проверка перед обработкой входящего сообщения."""
    # Минута — узкое горло, проверяем её первой
    d_min = await _check_sliding_window(
        key=f"rl:msg:min:{telegram_id}",
        window_seconds=60,
        limit=RATE_LIMITS["messages_per_minute"],
    )
    if not d_min.allowed:
        return d_min
    return await _check_sliding_window(
        key=f"rl:msg:hour:{telegram_id}",
        window_seconds=3600,
        limit=RATE_LIMITS["messages_per_hour"],
    )


async def check_payment_attempt(telegram_id: int) -> LimitDecision:
    """Платежи лимитируем строго (fail-closed): двойная оплата дороже отказа."""
    return await _check_sliding_window(
        key=f"rl:pay:hour:{telegram_id}",
        window_seconds=3600,
        limit=RATE_LIMITS["payment_attempts_per_hour"],
        fail_open=False,
    )


async def add_llm_tokens(telegram_id: int, tokens: int) -> LimitDecision:
    """Учитываем токены — НЕ запрещаем заранее, только пост-факт.

    Возвращаем decision: если пробили потолок 50k/day — следующий ответ
    LLM не пойдёт, ответим fallback'ом.
    """
    r = _get_redis()
    if not r:
        return LimitDecision(
            allowed=True, name="tokens", used=0, limit=RATE_LIMITS["llm_tokens_per_day"]
        )
    try:
        key = f"rl:tok:day:{telegram_id}"
        used = int(await r.incrby(key, tokens))
        await r.expire(key, 24 * 3600 + 60)
        limit = RATE_LIMITS["llm_tokens_per_day"]
        return LimitDecision(
            allowed=used <= limit,
            name="tokens",
            used=used,
            limit=limit,
        )
    except Exception as e:
        logger.warning("Token counter Redis error: %s", e)
        return LimitDecision(
            allowed=True, name="tokens", used=0, limit=RATE_LIMITS["llm_tokens_per_day"]
        )


# --------------- F10: Global hourly LLM budget ---------------

# Константы (можно переопределить через env в будущем)
_GLOBAL_HOURLY_BUDGET_RUB = 500
_HAIKU_INPUT_KOPECKS_PER_1K = 25   # ~0.25₽ за 1k input tokens (proxyapi.ru)
_HAIKU_OUTPUT_KOPECKS_PER_1K = 125  # ~1.25₽ за 1k output tokens


def estimate_cost_kopecks(input_tokens: int, output_tokens: int) -> int:
    """Грубая оценка стоимости вызова в копейках (Haiku 4.5 через proxyapi.ru)."""
    in_cost = (input_tokens / 1000) * _HAIKU_INPUT_KOPECKS_PER_1K
    out_cost = (output_tokens / 1000) * _HAIKU_OUTPUT_KOPECKS_PER_1K
    return max(1, int(in_cost + out_cost))


async def check_global_llm_budget() -> LimitDecision:
    """Проверяет глобальный почасовой бюджет LLM.

    fail_open=True: при недоступности Redis пропускаем запрос (LLM дешевле downtime).
    """
    r = _get_redis()
    if not r:
        return LimitDecision(allowed=True, name="global_llm_budget", used=0,
                             limit=_GLOBAL_HOURLY_BUDGET_RUB * 100)
    try:
        from datetime import datetime as _dt
        key = f"llm_budget:{_dt.now().strftime('%Y%m%d%H')}"
        spent = int(await r.get(key) or 0)
        limit = _GLOBAL_HOURLY_BUDGET_RUB * 100  # в копейках
        return LimitDecision(
            allowed=spent < limit,
            name="global_llm_budget",
            used=spent,
            limit=limit,
        )
    except Exception as e:
        logger.warning("Global LLM budget check Redis error: %s — allowing", e)
        return LimitDecision(allowed=True, name="global_llm_budget", used=0,
                             limit=_GLOBAL_HOURLY_BUDGET_RUB * 100)


async def track_global_llm_cost(input_tokens: int, output_tokens: int) -> None:
    """Учитывает стоимость LLM-вызова в глобальном почасовом счётчике."""
    r = _get_redis()
    if not r:
        return
    try:
        from datetime import datetime as _dt
        key = f"llm_budget:{_dt.now().strftime('%Y%m%d%H')}"
        kopecks = estimate_cost_kopecks(input_tokens, output_tokens)
        await r.incrby(key, kopecks)
        await r.expire(key, 3600 + 60)
    except Exception as e:
        logger.warning("Global LLM cost tracking error: %s", e)


async def check_llm_quota(telegram_id: int) -> LimitDecision:
    """Заглядываем не превышен ли дневной потолок (без инкремента)."""
    r = _get_redis()
    if not r:
        return LimitDecision(
            allowed=True, name="tokens", used=0, limit=RATE_LIMITS["llm_tokens_per_day"]
        )
    try:
        used = int(await r.get(f"rl:tok:day:{telegram_id}") or 0)
        limit = RATE_LIMITS["llm_tokens_per_day"]
        return LimitDecision(
            allowed=used < limit,
            name="tokens",
            used=used,
            limit=limit,
        )
    except Exception:
        return LimitDecision(
            allowed=True, name="tokens", used=0, limit=RATE_LIMITS["llm_tokens_per_day"]
        )
