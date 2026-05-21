"""Регрессия: видео-разбор в Plus подписан как «команда EDL OS», не как
персонально Екатерина / Катя. Решение зафиксировано 21.05.2026.

ИП «Жиганова Екатерина Викторовна» — это юр.идентификатор оператора
данных, его трогать не нужно (см. offer.py, consent.py, шаблоны footer).
Этот тест проверяет именно атрибуцию видео-разбора.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


CLIENT_VIDEO_SURFACES = [
    "src/bot/texts.py",
    "src/bot/handlers/checkup.py",
    "src/bot/handlers/audit.py",
    "src/knowledge_base/02_products_pricing.md",
    "src/knowledge_base/06_objections_handling.md",
    "src/knowledge_base/07_faq.json",
    "src/templates/checkup_report.html",
    "src/templates/checkup_report_v2.html",
    "src/prompts/base.md",
    "src/core/checkup_video_script.py",
]

# Личные атрибуции, которых не должно быть в клиентских поверхностях
# в контексте видео-разбора.
FORBIDDEN_PHRASES = [
    "видео-разбор от Кати",
    "видео от Кати",
    "видео-разбора от Кати",
    "видеоразбор от Кати",
    "видео-разбор от Екатерины Жигановой",
    "от Екатерины Жигановой",
    "от Кати лично",
    "лично Катя",
    "review by Катерина",
    "review by Катя",
    "Катя пересоберёт",
]


@pytest.mark.parametrize("relpath", CLIENT_VIDEO_SURFACES)
def test_client_video_attribution_is_team(relpath: str) -> None:
    path = ROOT / relpath
    if not path.exists():
        pytest.skip(f"{relpath} not present")
    content = path.read_text(encoding="utf-8")
    found = [p for p in FORBIDDEN_PHRASES if p in content]
    assert not found, (
        f"{relpath} attributes video personally — use «команда EDL OS» "
        f"instead. Found: {found}"
    )
