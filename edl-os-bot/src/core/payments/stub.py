"""Stub-провайдер: оплата помечается админом вручную.

Используется в PAYMENT_MODE=stub (по умолчанию на май-июнь 2026, пока
ЮKassa проходит модерацию). Бот не генерирует invoice — Application
создаётся со status=awaiting_manual_payment, Иван/Катя помечают
/mark_paid <app_id> вручную после прихода денег.
"""
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class StubInvoice:
    inv_id: int
    amount_rub: float
    description: str
    email: str | None
    user_telegram_id: int


class StubPaymentClient:
    """Заглушка — не делает реальных вызовов, всё через mark-paid."""

    @property
    def configured(self) -> bool:
        return True

    def build_invoice_url(self, invoice: StubInvoice) -> str | None:
        return None  # сигнал в audit.py: показать «ждите ссылку от Ивана»
