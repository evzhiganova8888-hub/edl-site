"""FAQ rules-based — поиск по ключевым словам в 11 Q&A (§7.8 ТЗ v3).

Без LLM, чтобы исключить галлюцинации. LLM-fallback подключим в Спринте 4.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_FAQ_JSON = Path(__file__).resolve().parent.parent / "knowledge_base" / "07_faq.json"


@dataclass(slots=True, frozen=True)
class FaqItem:
    idx: int
    question: str
    answer: str
    keywords: tuple[str, ...]


# Ключевые слова на каждый вопрос — задают «попадание» при поиске.
# Порядок соответствует порядку в knowledge_base/07_faq.json.
_KEYWORDS: tuple[tuple[str, ...], ...] = (
    ("чекап", "демо", "отлич", "разниц"),  # 1
    ("ндс", "антидроблен", "налог", "дроблен", "54.1"),  # 2
    ("безопасн", "налогов", "риск", "уязвим"),  # 3
    ("ниш", "сегмент", "произв", "опт", "услуг", "маркетплейс"),  # 4
    ("гарантия", "возврат", "защит"),  # 5
    ("зачет", "зачёт", "9 000", "9000", "диагностик"),  # 6
    ("закрое", "закроет", "что если", "пропад", "данны", "автоном"),  # 7
    ("остановить", "спринт", "защита", "этап"),  # 8
    ("google", "sheet", "tg", "telegram", "стек", "1с"),  # 9
    ("стоит", "стоимост", "цена", "тариф", "сколько"),  # 10
    ("кто", "команда", "ката", "екатери", "иван", "работ"),  # 11
)


@lru_cache(maxsize=1)
def _load() -> tuple[FaqItem, ...]:
    if not _FAQ_JSON.exists():
        return ()
    try:
        raw = json.loads(_FAQ_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ()
    out: list[FaqItem] = []
    for i, item in enumerate(raw):
        kw = _KEYWORDS[i] if i < len(_KEYWORDS) else ()
        out.append(
            FaqItem(
                idx=i + 1,
                question=str(item.get("question", "")),
                answer=str(item.get("answer", "")),
                keywords=kw,
            )
        )
    return tuple(out)


def all_items() -> tuple[FaqItem, ...]:
    return _load()


def get_by_index(idx: int) -> FaqItem | None:
    items = _load()
    if 1 <= idx <= len(items):
        return items[idx - 1]
    return None


_WORD_SPLIT = re.compile(r"[^а-яёa-z0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _WORD_SPLIT.split(text or "") if t}


def search(query: str) -> FaqItem | None:
    """Ищет лучший FAQ-айтем по ключевым словам. Если нет совпадений — None."""
    items = _load()
    if not items or not query:
        return None
    q_lower = query.lower()
    q_tokens = _tokenize(query)

    best: tuple[int, FaqItem | None] = (0, None)
    for item in items:
        score = 0
        # Совпадение по ключевым словам (фрагменты)
        for kw in item.keywords:
            if kw in q_lower:
                score += 2
        # Совпадение по словам в самом вопросе
        question_tokens = _tokenize(item.question)
        score += len(q_tokens & question_tokens)
        if score > best[0]:
            best = (score, item)
    return best[1] if best[0] >= 2 else None
