"""Anthropic Claude Haiku 4.5 — обёртка с prompt caching (§2.1 ТЗ v3).

В LLM передаём только обезличенный текст (см. core/pd_sanitize.py).
"""
from __future__ import annotations

import logging

from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.pd_sanitize import sanitize
from src.core.prompts import build_system_prompt

logger = logging.getLogger(__name__)


_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def reply(
    *,
    user_text: str,
    segment: str,
    stage: str = "cold",
    history: list[dict[str, str]] | None = None,
    vitaconsult_public: bool | None = None,
) -> tuple[str, int]:
    """Returns (response_text, total_tokens). Caches static system prompt."""
    client = get_client()
    safe_text = sanitize(user_text)
    system_blocks = build_system_prompt(
        segment=segment, stage=stage, vitaconsult_public=vitaconsult_public
    )

    messages: list[dict[str, str]] = list(history or [])
    messages.append({"role": "user", "content": safe_text})

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        system=system_blocks,
        messages=messages,
    )

    text_parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
    answer = "\n".join(text_parts).strip()
    total_tokens = response.usage.input_tokens + response.usage.output_tokens
    return answer, total_tokens
