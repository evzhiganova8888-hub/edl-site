"""Hand-off SLA — таблица по сегментам."""
from src.core.handoff import HANDOFF_RULES, get_rule


def test_manufacturing_4h_phone():
    rule = get_rule("manufacturing")
    assert rule.channel == "phone_or_email"
    assert rule.sla_hours == 4


def test_marketplace_accounting_1h_dm():
    rule = get_rule("marketplace_accounting")
    assert rule.channel == "direct_dm"
    assert rule.sla_hours == 1


def test_services_legal_24h_tg_or_email():
    rule = get_rule("services_legal")
    assert rule.channel == "tg_or_email"
    assert rule.sla_hours == 24


def test_other_fallback():
    rule = get_rule(None)
    assert rule.channel == "tg_or_email"


def test_all_segments_in_table():
    needed = {
        "manufacturing",
        "wholesale",
        "services_legal",
        "services_it",
        "services_marketing_agency",
        "b2b_saas",
        "marketplace_accounting",
        "marketplace_logistics",
        "other",
    }
    assert needed <= set(HANDOFF_RULES.keys())
