"""SoT v1.4 §14.2 — запреты в текстах бота.

Источник правды (17.05.2026) явно запрещает старые формулировки про
30-минутный звонок, 48 часов, PDF 5-7 страниц, Robokassa, 7 рабочих дней,
90-дневный план — всё это уже не соответствует реальности продукта (Чекап
теперь = 20 вопросов в боте, 24 часа на PDF, ЮKassa).

Если кто-то откатит texts.py — этот тест упадёт.
"""
from __future__ import annotations

from src.bot import texts


FORBIDDEN_IN_AUDIT_INTRO = [
    "30-минутный звонок",
    "48 часов",
    "5–7 страниц",
    "5-7 страниц",
    "7 рабочих дней",
    "90-дневный план",
    "90 дней",
    "FigJam",  # Q9 в SoT — пока не подтверждено, что генерируется
]


def test_audit_intro_no_forbidden_phrases():
    intro = texts.AUDIT_INTRO
    for phrase in FORBIDDEN_IN_AUDIT_INTRO:
        assert phrase not in intro, f"AUDIT_INTRO ещё содержит запрещённое: {phrase!r}"


def test_audit_intro_mentions_real_flow():
    """20 вопросов / 24 часа / автоматическое видео в течение 24 часов."""
    intro = texts.AUDIT_INTRO
    assert "20 вопросов" in intro
    assert "24 часа" in intro
    assert "автомат" in intro.lower()


def test_payment_succeeded_no_call_promise():
    """SoT: после оплаты — сразу /checkup, без обещания звонка."""
    txt = texts.PAYMENT_SUCCEEDED
    assert "звонк" not in txt.lower(), "После оплаты звонок не обещаем"
    assert "/checkup" in txt


def test_manual_payment_no_robokassa():
    assert "Robokassa" not in texts.MANUAL_PAYMENT_SUBMITTED
    assert "Robokassa" not in texts.PAYMENT_NOT_CONFIGURED


def test_refund_text_says_yookassa_not_robokassa():
    assert "Robokassa" not in texts.REFUND_REQUESTED
    assert "ЮKassa" in texts.REFUND_REQUESTED or "YooKassa" in texts.REFUND_REQUESTED


def test_demo_access_text_has_template_slots():
    """Шаблон формируется через .format(plan_suffix=..., plus_video_line=...)."""
    assert "{plan_suffix}" in texts.CHECKUP_DEMO_ACCESS_GRANTED
    assert "{plus_video_line}" in texts.CHECKUP_DEMO_ACCESS_GRANTED
