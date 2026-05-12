"""Сборка системного промпта с многоуровневым prompt caching.

Anthropic поддерживает до 4 cache breakpoints. Мы делим промпт на 3 cache-блока:
  Block 1 (shared): BASE + OUTPUT_FORMAT + глобальные KB файлы
                    (методология, гарантия, возражения, source-of-truth, pricing).
                    Один кеш на всех пользователей.
  Block 2 (per-segment): VERTICAL[segment] + HANDOFF[segment] + кейсы для сегмента.
                    Кеш на каждый сегмент (8+1).
  Block 3 (per-stage): STAGE[stage] + recap + flags. Без кеша (динамика).

До оптимизации: 1 cache-блок (BASE + ВСЕ verticals + ВСЕ stages + ВСЕ handoff)
→ для каждой комбинации segment×stage отдельный кеш, hit rate ~50%.

После: shared Block 1 для всех, Block 2 кешируется по сегменту → cache hit
rate растёт до ~85%, цена первого запроса в сегменте падает на ~50%.

См. docs/threat_model.md и продакт-анализ дороговизны.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.core.config import settings

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"

# Какие KB-файлы идут в shared Block 1 (одинаковы для всех).
# `07_faq.json` НЕ включается — FAQ работает через rules-based в /faq команде,
# в свободном AI-диалоге FAQ-знания нужны редко (см. опцию B оптимизации).
_GLOBAL_KB_FILES = (
    "01_source_of_truth.md",
    "02_products_pricing.md",
    "03_methodology_4_layers.md",
    "05_refund_guarantee.md",
    "06_objections_handling.md",
)

# `04_cases_anonymized.md` идёт в Block 2 (по сегменту), потому что в нём
# 8 разных кейсов — релевантен только один.


@lru_cache(maxsize=32)
def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _vertical_block(segment: str) -> str:
    candidate = _PROMPTS_DIR / "verticals" / f"{segment}.md"
    if not candidate.exists():
        candidate = _PROMPTS_DIR / "verticals" / "other.md"
    return _read(candidate)


def _stage_block(stage: str) -> str:
    candidate = _PROMPTS_DIR / "stages" / f"{stage}.md"
    if not candidate.exists():
        candidate = _PROMPTS_DIR / "stages" / "cold.md"
    return _read(candidate)


def _handoff_block(segment: str) -> str:
    candidate = _PROMPTS_DIR / "handoff" / f"{segment}.md"
    if not candidate.exists():
        candidate = _PROMPTS_DIR / "handoff" / "other.md"
    return _read(candidate)


def _global_knowledge_base() -> str:
    """Файлы из `_GLOBAL_KB_FILES` — те же для всех сегментов."""
    parts = []
    for fname in _GLOBAL_KB_FILES:
        text = _read(_KB_DIR / fname)
        if text:
            parts.append(f"### {Path(fname).stem}\n\n{text}")
    return "\n\n".join(parts)


@lru_cache(maxsize=1)
def _cases_section() -> str:
    """Кейсы (04_cases_anonymized.md) — общий файл, но для оптимизации
    идёт в Block 2 (per-segment), т.к. это динамический контент.

    В будущем можно разрезать по сегментам, но размер файла (~3K токенов)
    не критичен, оставляем целиком в Block 2.
    """
    text = _read(_KB_DIR / "04_cases_anonymized.md")
    return f"### cases\n\n{text}" if text else ""


def _runtime_flags(*, vitaconsult_public: bool) -> str:
    return f"VITACONSULT_PUBLIC = {str(vitaconsult_public).lower()}"


@lru_cache(maxsize=1)
def _shared_block_text() -> str:
    """Block 1: одинаковый для всех — макс. cache hit rate."""
    base = _read(_PROMPTS_DIR / "base.md")
    output_format = _read(_PROMPTS_DIR / "output_format.md")
    return "\n\n".join(filter(None, [base, _global_knowledge_base(), output_format]))


@lru_cache(maxsize=16)
def _segment_block_text(segment: str) -> str:
    """Block 2: специфика сегмента. Кеш на каждый segment."""
    return "\n\n".join(
        filter(
            None,
            [
                _vertical_block(segment),
                _handoff_block(segment),
                _cases_section(),
            ],
        )
    )


def build_system_prompt(
    *,
    segment: str,
    stage: str,
    vitaconsult_public: bool | None = None,
    recap_snippet: str | None = None,
) -> list[dict]:
    """Многоуровневые блоки для Anthropic prompt caching.

    Block 1 (cache, shared): BASE + global KB + OUTPUT_FORMAT
    Block 2 (cache, per-segment): VERTICAL + HANDOFF + cases
    Block 3 (no cache, per-request): STAGE + recap + runtime flags
    """
    flag_value = bool(settings.vitaconsult_public) if vitaconsult_public is None else vitaconsult_public

    blocks: list[dict] = [
        {
            "type": "text",
            "text": _shared_block_text(),
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": _segment_block_text(segment),
            "cache_control": {"type": "ephemeral"},
        },
    ]

    # Block 3 — динамика, не кешируется
    dynamic_parts = [_stage_block(stage)]
    if recap_snippet:
        dynamic_parts.append(recap_snippet)
    dynamic_parts.append(_runtime_flags(vitaconsult_public=flag_value))
    blocks.append(
        {
            "type": "text",
            "text": "\n\n".join(filter(None, dynamic_parts)),
        }
    )
    return blocks
