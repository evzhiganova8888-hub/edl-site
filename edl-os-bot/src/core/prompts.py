"""Сборка системного промпта из BASE → VERTICAL → STAGE → HANDOFF → KB → OUTPUT.

Файлы лежат в src/prompts/. Здесь мы их читаем и собираем массив system-блоков
с пометкой cache_control для prompt caching (§6 ТЗ v3).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.core.config import settings

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"


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


def _knowledge_base() -> str:
    if not _KB_DIR.exists():
        return ""
    parts = []
    for path in sorted(_KB_DIR.glob("*.md")):
        parts.append(f"### {path.stem}\n\n{_read(path)}")
    return "\n\n".join(parts)


def _runtime_flags(*, vitaconsult_public: bool) -> str:
    return f"VITACONSULT_PUBLIC = {str(vitaconsult_public).lower()}"


def build_system_prompt(
    *,
    segment: str,
    stage: str,
    vitaconsult_public: bool | None = None,
    recap_snippet: str | None = None,
) -> list[dict]:
    """Возвращает массив system-блоков для Anthropic API.

    Статическая часть промпта помечается `cache_control: ephemeral` — Anthropic
    кэширует её ($0.08 вместо $1 за 1M). Recap и runtime-флаги — отдельными
    блоками без кэширования (динамические).

    `vitaconsult_public` передаётся динамически (из core.flags). Если None —
    fallback на env-значение.
    `recap_snippet` — короткая сводка прошлых обращений (см. core.memory),
    если пользователь возвращается через 24+ ч.
    """
    base = _read(_PROMPTS_DIR / "base.md")
    output_format = _read(_PROMPTS_DIR / "output_format.md")

    static_part = "\n\n".join(
        filter(
            None,
            [
                base,
                _vertical_block(segment),
                _stage_block(stage),
                _handoff_block(segment),
                _knowledge_base(),
                output_format,
            ],
        )
    )

    flag_value = bool(settings.vitaconsult_public) if vitaconsult_public is None else vitaconsult_public

    blocks: list[dict] = [
        {
            "type": "text",
            "text": static_part,
            "cache_control": {"type": "ephemeral"},
        },
    ]
    if recap_snippet:
        blocks.append({"type": "text", "text": recap_snippet})
    blocks.append(
        {
            "type": "text",
            "text": _runtime_flags(vitaconsult_public=flag_value),
        }
    )
    return blocks
