"""Правила hand-off по сегментам (§12 ТЗ v3)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from src.core.working_hours import humanize_window, is_working_now, next_business_window


@dataclass(slots=True)
class HandoffRule:
    channel: str  # phone_or_email | tg_or_email | direct_dm
    sla_hours: int
    sla_label: str


HANDOFF_RULES: dict[str, HandoffRule] = {
    "manufacturing": HandoffRule("phone_or_email", 4, "4 рабочих часа"),
    "wholesale": HandoffRule("phone_or_email", 4, "4 рабочих часа"),
    "services_legal": HandoffRule("tg_or_email", 24, "24 рабочих часа"),
    "services_it": HandoffRule("tg_or_email", 24, "24 рабочих часа"),
    "services_marketing_agency": HandoffRule("tg_or_email", 24, "24 рабочих часа"),
    "b2b_saas": HandoffRule("tg_or_email", 24, "24 рабочих часа"),
    "marketplace_accounting": HandoffRule("direct_dm", 1, "1 рабочий час"),
    "marketplace_logistics": HandoffRule("direct_dm", 1, "1 рабочий час"),
    "other": HandoffRule("tg_or_email", 24, "24 рабочих часа"),
}


def get_rule(segment: str | None) -> HandoffRule:
    return HANDOFF_RULES.get(segment or "other", HANDOFF_RULES["other"])


def handoff_phrase(segment: str | None) -> str:
    """Формулировка для пользователя с учётом рабочих часов."""
    rule = get_rule(segment)
    if is_working_now():
        return f"Иван свяжется в течение {rule.sla_label}."
    deadline = next_business_window() + timedelta(hours=rule.sla_hours)
    return f"Сейчас нерабочее время. Иван свяжется {humanize_window(deadline)}."
