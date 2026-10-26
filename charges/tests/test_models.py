from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from charges.models import Charge, ChargeStateError

pytestmark = pytest.mark.django_db


def test_new_charge_is_pending_with_generated_txid(make_charge):
    charge = make_charge()

    assert charge.status == Charge.Status.PENDING
    assert len(charge.txid) == 25
    assert charge.txid.isalnum()


def test_pix_payload_carries_amount_and_txid(make_charge):
    charge = make_charge(amount=Decimal("99.90"))

    payload = charge.pix_payload()

    assert "540599.90" in payload
    assert f"0525{charge.txid}" in payload


def test_mark_paid_from_overdue_records_payment_time(make_charge):
    charge = make_charge(status=Charge.Status.OVERDUE)

    charge.mark_paid()

    charge.refresh_from_db()
    assert charge.status == Charge.Status.PAID
    assert charge.paid_at is not None


def test_mark_paid_rejects_canceled_charge(make_charge):
    charge = make_charge(status=Charge.Status.CANCELED)

    with pytest.raises(ChargeStateError, match="canceled"):
        charge.mark_paid()


def test_cancel_pending_charge(make_charge):
    charge = make_charge()

    charge.cancel()

    charge.refresh_from_db()
    assert charge.status == Charge.Status.CANCELED


def test_cancel_rejects_paid_charge(make_charge):
    charge = make_charge(status=Charge.Status.PAID)

    with pytest.raises(ChargeStateError, match="paid"):
        charge.cancel()


def test_database_rejects_non_positive_amount(make_charge):
    with pytest.raises(IntegrityError):
        make_charge(amount=Decimal("0"))


def test_payer_document_must_be_cpf_or_cnpj_digits(make_charge):
    charge = make_charge(payer_document="123.456.789-01")

    with pytest.raises(ValidationError, match="payer_document"):
        charge.full_clean()


def test_is_overdue_on_compares_due_date(make_charge):
    charge = make_charge(due_date=date(2026, 1, 10))

    assert charge.is_overdue_on(date(2026, 1, 11))
    assert not charge.is_overdue_on(date(2026, 1, 10))
