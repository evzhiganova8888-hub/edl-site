"""StubPaymentClient: всегда configured=True, build_invoice_url возвращает None."""
from src.core.payments.stub import StubInvoice, StubPaymentClient


def test_configured_always_true():
    assert StubPaymentClient().configured is True


def test_build_invoice_url_returns_none():
    inv = StubInvoice(
        inv_id=1,
        amount_rub=9000.0,
        description="Audit",
        email="user@example.com",
        user_telegram_id=12345,
    )
    assert StubPaymentClient().build_invoice_url(inv) is None


def test_stub_invoice_immutable():
    inv = StubInvoice(inv_id=2, amount_rub=14000.0, description="Plus", email=None, user_telegram_id=99)
    assert inv.amount_rub == 14000.0
    try:
        inv.amount_rub = 0  # type: ignore[misc]
        assert False, "should be frozen"
    except (AttributeError, TypeError):
        pass
