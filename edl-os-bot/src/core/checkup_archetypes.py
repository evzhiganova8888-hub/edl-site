"""6 архетипов MVP + fallback-логика (ТЗ Чекап Plus v2.0 §3.5).

Архетип = пара (segment × stage). По нему персонализируются:
- примеры хороших ответов на 16 SPIN-вопросов;
- 3 экрана-вставки между блоками вопросов;
- fallback dataset для PDF на случай Claude failure.

В v1.0 поддерживаются 6 пар точно. Остальные 18 — fallback по ближайшему
сегменту/стадии.
"""
from __future__ import annotations

from typing import Literal

ArchetypeKey = Literal[
    "anna_command",            # edu × Команда
    "anna_structure",          # edu × Структура
    "dmitri_structure",        # mp × Структура
    "artem_command",           # it × Команда
    "pro_services_structure",  # serv × Структура
    "nds_first_command",       # prod × Команда
]

MVP_ARCHETYPES: dict[tuple[str, str], ArchetypeKey] = {
    ("edu", "Команда"): "anna_command",
    ("edu", "Структура"): "anna_structure",
    ("mp", "Структура"): "dmitri_structure",
    ("it", "Команда"): "artem_command",
    ("serv", "Структура"): "pro_services_structure",
    ("prod", "Команда"): "nds_first_command",
}

# Соседство сегментов для fallback. Если точного совпадения нет —
# идём к ближайшему «соседу» по содержанию.
_SEGMENT_NEIGHBORS: dict[str, str] = {
    "edu": "serv",
    "mp": "prod",
    "it": "serv",
    "prod": "mp",
    "serv": "edu",
    "saas": "it",
    "other": "edu",
}

# Канонический порядок стадий (ТЗ §1.1)
_STAGE_ORDER = ("Старт", "Команда", "Структура", "Зрелость")


def _normalize_stage(stage: str | None) -> str:
    """Нормализует ярлык стадии. Default — Команда."""
    if not stage:
        return "Команда"
    s = stage.strip()
    # Маппинг возможных альтернативных написаний из старой Mini-Чекап
    aliases = {
        "start": "Старт",
        "team": "Команда",
        "structure": "Структура",
        "maturity": "Зрелость",
    }
    return aliases.get(s.lower(), s)


def get_archetype_for_user(segment: str | None, stage: str | None) -> ArchetypeKey:
    """Точный матч → fallback по сегменту-соседу → дефолт anna_command.

    Контракт ТЗ §3.5:
    1. Если пара есть в MVP — возвращаем точный архетип.
    2. Если есть архетип для того же сегмента — берём его (ближайшая стадия).
    3. Если сегмент-сосед даёт хоть один архетип — берём.
    4. Иначе — anna_command (главный архетип edu × Команда).
    """
    seg = (segment or "other").lower()
    st = _normalize_stage(stage)

    # 1. Точный матч
    if (seg, st) in MVP_ARCHETYPES:
        return MVP_ARCHETYPES[(seg, st)]

    # 2. Тот же сегмент, любая стадия (ближайшая)
    same_seg = [
        (s_pair, archetype)
        for s_pair, archetype in MVP_ARCHETYPES.items()
        if s_pair[0] == seg
    ]
    if same_seg:
        # Берём первую попавшуюся — мы можем выбрать ближайшую стадию,
        # но в MVP это упрощено
        return same_seg[0][1]

    # 3. Сегмент-сосед
    neighbor = _SEGMENT_NEIGHBORS.get(seg, "edu")
    neighbor_arches = [
        archetype
        for s_pair, archetype in MVP_ARCHETYPES.items()
        if s_pair[0] == neighbor
    ]
    if neighbor_arches:
        return neighbor_arches[0]

    # 4. Дефолт
    return "anna_command"


# ── Метаданные архетипов для PDF/видео-шпаргалок ─────────────────────────────


ARCHETYPE_META: dict[ArchetypeKey, dict[str, str]] = {
    "anna_command": {
        "name": "Анна",
        "segment_label": "Онлайн-школа",
        "segment_label_genitive": "онлайн-школ",
        "stage_current": "Команда",
        "stage_next": "Структура",
        "typical_revenue": "15–60М ₽",
        "typical_team_size": "10–25 человек",
        "typical_pain": "ICP широкий в маркетинге, узкий в продажах; команда растёт быстрее процессов",
    },
    "anna_structure": {
        "name": "Анна.Структура",
        "segment_label": "Онлайн-школа",
        "segment_label_genitive": "онлайн-школ",
        "stage_current": "Структура",
        "stage_next": "Зрелость",
        "typical_revenue": "60–200М ₽",
        "typical_team_size": "25–50 человек",
        "typical_pain": "кризис координации; стратегия в голове фаундера, не в KPI команд",
    },
    "dmitri_structure": {
        "name": "Дмитрий",
        "segment_label": "Marketplace-сервис для бухгалтерии",
        "segment_label_genitive": "marketplace-сервисов",
        "stage_current": "Структура",
        "stage_next": "Зрелость",
        "typical_revenue": "60–200М ₽",
        "typical_team_size": "25–50 человек",
        "typical_pain": "концентрация на крупных клиентах; юнит-экономика по сегментам",
    },
    "artem_command": {
        "name": "Артём",
        "segment_label": "IT-агентство",
        "segment_label_genitive": "IT-агентств",
        "stage_current": "Команда",
        "stage_next": "Структура",
        "typical_revenue": "15–60М ₽",
        "typical_team_size": "10–25 человек",
        "typical_pain": "customer concentration; маржа проектов плавает",
    },
    "pro_services_structure": {
        "name": "Pro Services",
        "segment_label": "Юридическая/консалтинговая компания",
        "segment_label_genitive": "профессиональных услуг",
        "stage_current": "Структура",
        "stage_next": "Зрелость",
        "typical_revenue": "60–200М ₽",
        "typical_team_size": "25–50 человек",
        "typical_pain": "personal-led бизнес у partners, не масштабируется системой",
    },
    "nds_first_command": {
        "name": "НДС-впервые",
        "segment_label": "Производство/опт",
        "segment_label_genitive": "производств",
        "stage_current": "Команда",
        "stage_next": "Структура",
        "typical_revenue": "15–60М ₽",
        "typical_team_size": "10–25 человек",
        "typical_pain": "НДС-2026 порог 20М ₽ пробивается в Q1; cashflow gap при переходе",
    },
}


# ── Бенчмарки для сегмент × стадия (статика 6 ячеек matrix, ТЗ §5.3.5) ────


SEGMENT_STAGE_BENCHMARKS: dict[tuple[str, str], int] = {
    ("edu", "Команда"): 54,
    ("edu", "Структура"): 62,
    ("mp", "Структура"): 65,
    ("it", "Команда"): 56,
    ("serv", "Структура"): 58,
    ("prod", "Команда"): 50,
}


def get_benchmark_avg(segment: str | None, stage: str | None) -> int:
    """Средний Score для сегмент × стадия. Дефолт 50 для остальных."""
    seg = (segment or "other").lower()
    st = _normalize_stage(stage)
    return SEGMENT_STAGE_BENCHMARKS.get((seg, st), 50)


# ── Stage weights для расчёта общего Score (ТЗ §5.3.4) ──────────────────────


STAGE_WEIGHTS: dict[str, dict[str, float]] = {
    "Старт": {"strategy": 0.35, "funnel": 0.25, "ops": 0.15, "money": 0.25},
    "Команда": {"strategy": 0.30, "funnel": 0.30, "ops": 0.20, "money": 0.20},
    "Структура": {"strategy": 0.25, "funnel": 0.25, "ops": 0.30, "money": 0.20},
    "Зрелость": {"strategy": 0.30, "funnel": 0.20, "ops": 0.30, "money": 0.20},
}


def get_stage_weights(stage: str | None) -> dict[str, float]:
    return STAGE_WEIGHTS.get(_normalize_stage(stage), STAGE_WEIGHTS["Команда"])
