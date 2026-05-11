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


def _runtime_flags() -> str:
    return f"VITACONSULT_PUBLIC = {str(settings.vitaconsult_public).lower()}"


def build_system_prompt(*, segment: str, stage: str) -> list[dict]:
    """Возвращает массив system-блоков для Anthropic API.

    Все статические блоки помечаем `cache_control: ephemeral` — Anthropic
    кэширует их и берёт $0.08/1M вместо $1/1M.
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

    return [
        {
            "type": "text",
            "text": static_part,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": _runtime_flags(),
        },
    ]
