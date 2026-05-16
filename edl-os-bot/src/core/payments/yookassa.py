"""YooKassa клиент: построение платёжной ссылки + верификация callback.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from yookassa import Configuration, Payment
from src.core.config import settings

@dataclass(slots=True, frozen=True)
class YookassaInvoice:
    """Данные для построения invoice."""

    inv_id: int
    amount_rub: float
    description: str
    email: str | None
    user_telegram_id: int


class YookassaClient:
    """Тонкая обёртка над YooKassa API."""

    def __init__(
        self,
        *,
        account_id: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        self.account_id = account_id or getattr(settings, 'yookassa_account_id', None)
        self.secret_key = secret_key or getattr(settings, 'yookassa_secret_key', None)
        if self.account_id and self.secret_key:
            Configuration.account_id = self.account_id
            Configuration.secret_key = self.secret_key

    @property
    def configured(self) -> bool:
        return bool(self.account_id and self.secret_key)

    def build_invoice_url(self, invoice: YookassaInvoice) -> str:
        """Возвращает URL на платёжную форму YooKassa.
        """
        if not self.configured:
            return "https://yookassa.ru/demo"

        # Create payment
        payment = Payment.create({
            "amount": {
                "value": f"{invoice.amount_rub:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/edl_os_bot"
            },
            "capture": True,
            "description": invoice.description,
            "metadata": {
                "inv_id": str(invoice.inv_id),
                "user_telegram_id": str(invoice.user_telegram_id),
                "email": invoice.email or ""
            },
            "receipt": self._build_receipt(invoice)
        }, uuid.uuid4())

        return payment.confirmation.confirmation_url

    def _build_receipt(self, invoice: YookassaInvoice) -> dict:
        """Фискальный чек (54-ФЗ). УСН — sno=usn_income, tax=none."""
        if not invoice.email:
            # ЮKassa requires email or phone for receipt
            return {}
            
        return {
            "customer": {
                "email": invoice.email
            },
            "items": [
                {
                    "description": invoice.description,
                    "quantity": "1.00",
                    "amount": {
                        "value": f"{invoice.amount_rub:.2f}",
                        "currency": "RUB"
                    },
                    "vat_code": 1, # Без НДС
                    "payment_mode": "full_payment",
                    "payment_subject": "service"
                }
            ]
        }

    # For webhooks handling later
    def verify_result_callback(self, request_json: dict) -> dict | None:
        pass
