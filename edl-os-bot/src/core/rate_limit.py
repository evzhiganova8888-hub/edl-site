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
    *, key: str, window_seconds: int, limit: int, increment: int = 1
) -> LimitDecision:
    """ZSET sliding window: добавляем timestamp, чистим старые, считаем.

    Если Redis недоступен — пропускаем (failure-open). Это сознательное решение:
    лучше пропустить лишнее сообщение, чем заблокировать всех пользователей.
    """
    r = _get_redis()
    if not r:
        return LimitDecision(allowed=True, name=key, used=0, limit=limit)

    try:
        now = time.time()
        cutoff = now - window_seconds
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zcard(key)
        _, used = await pipe.execute()
        if used + increment > limit:
            # вычислим, когда освободится одно место
            oldest = await r.zrange(key, 0, 0, withscores=True)
            retry = None
            if oldest:
                retry = max(1, int(oldest[0][1] + window_seconds - now))
            return LimitDecision(
                allowed=False,
                name=key,
                used=used,
                limit=limit,
                retry_after_seconds=retry,
            )
        # Записываем
        member = f"{now}:{used + 1}"
        await r.zadd(key, {member: now})
        await r.expire(key, window_seconds + 10)
        return LimitDecision(
            allowed=True, name=key, used=used + increment, limit=limit
        )
    except Exception as e:
        logger.warning("Rate limit Redis error (%s) on %s — allowing", e, key)
        return LimitDecision(allowed=True, name=key, used=0, limit=limit)


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
    return await _check_sliding_window(
        key=f"rl:pay:hour:{telegram_id}",
        window_seconds=3600,
        limit=RATE_LIMITS["payment_attempts_per_hour"],
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
