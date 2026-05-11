"""Robokassa: подпись invoice + верификация ResultURL callback."""
import hashlib

from src.core.payments.robokassa import RobokassaClient, RobokassaInvoice


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest().lower()


def _make_client() -> RobokassaClient:
    return RobokassaClient(
        merchant_login="edl-test",
        password_1="pwd1",
        password_2="pwd2",
        is_test=True,
    )


def test_configured_false_by_default():
    c = RobokassaClient(merchant_login="", password_1="", password_2="", is_test=True)
    assert c.configured is False


def test_configured_true_when_all_set():
    assert _make_client().configured is True


def test_invoice_url_contains_required_params():
    invoice = RobokassaInvoice(
        inv_id=42,
        amount_rub=9000.0,
        description="Audit",
        email="user@example.com",
        user_telegram_id=12345,
    )
    url = _make_client().build_invoice_url(invoice)
    assert "MerchantLogin=edl-test" in url
    assert "OutSum=9000.00" in url
    assert "InvId=42" in url
    assert "Shp_user_id=12345" in url
    assert "IsTest=1" in url


def test_invoice_signature_correct():
    invoice = RobokassaInvoice(
        inv_id=42,
        amount_rub=9000.0,
        description="Audit",
        email=None,
        user_telegram_id=12345,
    )
    url = _make_client().build_invoice_url(invoice)
    expected = _md5("edl-test:9000.00:42:pwd1:Shp_user_id=12345")
    assert f"SignatureValue={expected}" in url


def test_verify_result_callback_valid():
    client = _make_client()
    sig = _md5("9000.00:42:pwd2:Shp_user_id=12345")
    params = {
        "OutSum": "9000.00",
        "InvId": "42",
        "SignatureValue": sig,
        "Shp_user_id": "12345",
    }
    cb = client.verify_result_callback(params)
    assert cb is not None
    assert cb.inv_id == 42
    assert cb.user_telegram_id == 12345
    assert cb.amount_rub == 9000.0


def test_verify_result_callback_bad_signature():
    client = _make_client()
    params = {
        "OutSum": "9000.00",
        "InvId": "42",
        "SignatureValue": "deadbeef" * 4,
        "Shp_user_id": "12345",
    }
    assert client.verify_result_callback(params) is None


def test_verify_result_callback_missing_fields():
    assert _make_client().verify_result_callback({}) is None
    assert _make_client().verify_result_callback({"OutSum": "100"}) is None
