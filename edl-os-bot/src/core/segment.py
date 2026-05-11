"""Segment detection (§2 ТЗ v3).

Приоритеты:
1. deep_link  (?start=audit_services_legal и т.д.)
2. inline-кнопки после /start
3. AI-классификатор на 2-м содержательном сообщении (Спринт 3)
4. Маркер-слова в тексте
5. Fallback: other / cold
"""
from __future__ import annotations

from dataclasses import dataclass

SEGMENTS = [
    "manufacturing",
    "wholesale",
    "services_legal",
    "services_it",
    "services_marketing_agency",
    "b2b_saas",
    "marketplace_accounting",
    "marketplace_logistics",
    "other",
]

SEGMENT_LABELS = {
    "manufacturing": "Производство",
    "wholesale": "Опт",
    "services_legal": "Юр-консалтинг",
    "services_it": "IT-консалтинг",
    "services_marketing_agency": "Маркетинговое агентство",
    "b2b_saas": "B2B SaaS",
    "marketplace_accounting": "Бухгалтерия для маркетплейсов",
    "marketplace_logistics": "Логистика для маркетплейсов",
    "other": "Другое",
}

STAGES = ["cold", "warm", "hot", "beta", "client"]

# Под-профили внутри сегмента — влияют только на выбор кейса.
SUB_PROFILES: dict[str, dict[str, list[str]]] = {
    "manufacturing": {
        "vat_first_time": ["усн", "первый раз", "впервые ндс"],
        "vat_increased": ["было 20", "повышение", "22 процента", "осн"],
        "consolidation_risk": ["дробление", "консолидация", "несколько ип", "несколько ооо"],
    },
    "services_legal": {
        "ai_threat": ["balance", "minerva", "lawhive", "ai заменит"],
        "margin_loss": ["маржа", "минус по проекту", "billable"],
    },
    "marketplace_accounting": {
        "tg_native": ["голосовуха", "voice", "канал", "бот-агрегатор"],
        "wb_specific": ["wb", "вб", "wildberries", "вайлдбериз"],
        "ozon_specific": ["ozon", "озон"],
    },
}

# Маркер-слова для базовой эвристики сегмента (если deep_link не пришёл).
SEGMENT_MARKERS: dict[str, list[str]] = {
    "manufacturing": ["производство", "цех", "1с упп", "мебель", "металл", "пищёв", "упаковк"],
    "wholesale": ["опт", "дистрибуц", "стройматериал", "fmcg", "1с торговля"],
    "services_legal": ["юр-бутик", "юристы", "юр-консалтинг", "налоговый консалтинг", "billable"],
    "services_it": ["1с внедрение", "sap", "bi-интегратор", "it-консалтинг", "utilization"],
    "services_marketing_agency": [
        "performance-агентство",
        "brand-агентство",
        "digital-агентство",
        "creative-студия",
    ],
    "b2b_saas": ["saas", "mrr", "churn", "plg", "dev-tool"],
    "marketplace_accounting": [
        "бухгалтерия wb",
        "бухгалтерия ozon",
        "бухгалтерия для маркетплейс",
        "витаконсалт",
    ],
    "marketplace_logistics": [
        "логистика wb",
        "логистика ozon",
        "fbo",
        "fbs",
        "биллинг по weight",
    ],
}

# Маппинг deep-link → сегмент.
DEEP_LINK_TO_SEGMENT: dict[str, str] = {
    "manufacturing": "manufacturing",
    "manufacturing_warm": "manufacturing",
    "wholesale": "wholesale",
    "audit_services_legal": "services_legal",
    "services_legal": "services_legal",
    "services_it": "services_it",
    "marketing_agency": "services_marketing_agency",
    "b2b_saas": "b2b_saas",
    "marketplace_accounting": "marketplace_accounting",
    "marketplace_logistics": "marketplace_logistics",
}


@dataclass(slots=True)
class SegmentDetection:
    segment: str
    sub_profile: str | None
    method: str  # deep_link | button | markers | ai | fallback


def detect_from_deep_link(payload: str | None) -> str | None:
    """`/start audit_services_legal` → services_legal."""
    if not payload:
        return None
    payload = payload.strip().lower()
    if payload in DEEP_LINK_TO_SEGMENT:
        return DEEP_LINK_TO_SEGMENT[payload]
    # `audit_<segment>` — берём правую часть
    for prefix in ("audit_", "demo_", "diagnostic_", "sprint_waitlist_"):
        if payload.startswith(prefix):
            tail = payload[len(prefix) :]
            if tail in DEEP_LINK_TO_SEGMENT:
                return DEEP_LINK_TO_SEGMENT[tail]
    return None


def detect_from_text(text: str) -> str | None:
    """Эвристика на маркер-слова. Возвращает первый совпавший сегмент или None."""
    if not text:
        return None
    lower = text.lower()
    for segment, markers in SEGMENT_MARKERS.items():
        if any(marker in lower for marker in markers):
            return segment
    return None


def detect_sub_profile(segment: str, text: str) -> str | None:
    if segment not in SUB_PROFILES or not text:
        return None
    lower = text.lower()
    for sub_profile, markers in SUB_PROFILES[segment].items():
        if any(marker in lower for marker in markers):
            return sub_profile
    return None


def detect(payload: str | None, text: str | None) -> SegmentDetection:
    seg = detect_from_deep_link(payload)
    if seg:
        sub = detect_sub_profile(seg, text or "")
        return SegmentDetection(segment=seg, sub_profile=sub, method="deep_link")
    if text:
        seg = detect_from_text(text)
        if seg:
            sub = detect_sub_profile(seg, text)
            return SegmentDetection(segment=seg, sub_profile=sub, method="markers")
    return SegmentDetection(segment="other", sub_profile=None, method="fallback")
