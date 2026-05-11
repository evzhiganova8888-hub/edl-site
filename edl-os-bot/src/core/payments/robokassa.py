"""Robokassa клиент: построение платёжной ссылки + верификация callback.

Документация: https://docs.robokassa.ru/

Поток:
1. Бот формирует invoice URL с подписью SignatureValue = md5(login:OutSum:InvId:Pass1[:UserData])
2. Пользователь оплачивает на стороне Robokassa
3. Robokassa дёргает ResultURL с подписью md5(OutSum:InvId:Pass2[:UserData])
4. Robokassa редиректит на SuccessURL с подписью md5(OutSum:InvId:Pass1)

Фискальный чек формируется через параметр Receipt (JSON, urlencoded).
ИП Жиганова на УСН — НДС «без НДС», предмет «услуга».
"""
from __future__ import annotations

import hashlib
import json
import urllib.parse
from dataclasses import dataclass

from src.core.config import settings

_BASE_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest().lower()


@dataclass(slots=True, frozen=True)
class RobokassaInvoice:
    """Данные для построения invoice."""

    inv_id: int
    amount_rub: float
    description: str
    email: str | None
    user_telegram_id: int


@dataclass(slots=True, frozen=True)
class RobokassaCallback:
    """Распарсенный ResultURL callback от Robokassa."""

    inv_id: int
    amount_rub: float
    signature: str
    user_telegram_id: int | None
    raw_params: dict[str, str]


class RobokassaClient:
    """Тонкая обёртка над Robokassa Merchant API."""

    def __init__(
        self,
        *,
        merchant_login: str | None = None,
        password_1: str | None = None,
        password_2: str | None = None,
        is_test: bool = True,
    ) -> None:
        self.merchant_login = merchant_login or settings.robokassa_merchant_login
        self.password_1 = password_1 or settings.robokassa_password_1
        self.password_2 = password_2 or settings.robokassa_password_2
        self.is_test = bool(is_test if is_test is not None else settings.robokassa_is_test)

    @property
    def configured(self) -> bool:
        return bool(self.merchant_login and self.password_1 and self.password_2)

    def build_invoice_url(self, invoice: RobokassaInvoice) -> str:
        """Возвращает URL на платёжную форму Robokassa.

        Подпись формируется как md5(login:OutSum:InvId:Pass1:Shp_user_id=...:Shp_email=...).
        Robokassa требует, чтобы Shp_* параметры были отсортированы в подписи и в URL.
        """
        out_sum = f"{invoice.amount_rub:.2f}"
        shp_params = {
            "Shp_user_id": str(invoice.user_telegram_id),
        }
        if invoice.email:
            shp_params["Shp_email"] = invoice.email

        # Подпись: login:OutSum:InvId:Pass1[:Shp_x=v:Shp_y=v...]
        shp_for_sig = ":".join(f"{k}={v}" for k, v in sorted(shp_params.items()))
        sig_base = f"{self.merchant_login}:{out_sum}:{invoice.inv_id}:{self.password_1}"
        if shp_for_sig:
            sig_base = f"{sig_base}:{shp_for_sig}"
        signature = _md5(sig_base)

        receipt = self._build_receipt(invoice)

        params = {
            "MerchantLogin": self.merchant_login,
            "OutSum": out_sum,
            "InvId": str(invoice.inv_id),
            "Description": invoice.description,
            "SignatureValue": signature,
            "Receipt": json.dumps(receipt, ensure_ascii=False),
            "Culture": "ru",
            "Encoding": "utf-8",
            **shp_params,
        }
        if invoice.email:
            params["Email"] = invoice.email
        if self.is_test:
            params["IsTest"] = "1"

        return f"{_BASE_URL}?{urllib.parse.urlencode(params)}"

    def _build_receipt(self, invoice: RobokassaInvoice) -> dict:
        """Фискальный чек (54-ФЗ). УСН — sno=usn_income, tax=none."""
        return {
            "sno": "usn_income",
            "items": [
                {
                    "name": invoice.description,
                    "quantity": 1,
                    "sum": invoice.amount_rub,
                    "payment_method": "full_payment",
                    "payment_object": "service",
                    "tax": "none",
                }
            ],
        }

    def verify_result_callback(self, params: dict[str, str]) -> RobokassaCallback | None:
        """Проверяет подпись ResultURL. Возвращает RobokassaCallback или None если signature не сошлась."""
        try:
            out_sum = str(params["OutSum"])
            inv_id = int(params["InvId"])
        except (KeyError, ValueError):
            return None
        signature = str(params.get("SignatureValue", "")).lower()
        if not signature:
            return None

        shp_params = {k: v for k, v in params.items() if k.startswith("Shp_")}
        shp_for_sig = ":".join(f"{k}={v}" for k, v in sorted(shp_params.items()))
        sig_base = f"{out_sum}:{inv_id}:{self.password_2}"
        if shp_for_sig:
            sig_base = f"{sig_base}:{shp_for_sig}"
        expected = _md5(sig_base)
        if expected != signature:
            return None

        user_id_str = shp_params.get("Shp_user_id")
        user_id = int(user_id_str) if user_id_str and user_id_str.isdigit() else None

        return RobokassaCallback(
            inv_id=inv_id,
            amount_rub=float(out_sum),
            signature=signature,
            user_telegram_id=user_id,
            raw_params=dict(params),
        )
