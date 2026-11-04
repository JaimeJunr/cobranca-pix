from datetime import date

import pytest

from charges.models import Charge, ChargeStateError, WebhookDelivery
from charges.services import mark_overdue_charges, pay_charge

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 25)


def test_mark_overdue_only_touches_pending_charges_past_due(make_charge):
    late = make_charge(due_date=date(2026, 10, 24))
    due_today = make_charge(due_date=TODAY)
    already_paid = make_charge(due_date=date(2026, 10, 1), status=Charge.Status.PAID)

    deliveries = mark_overdue_charges(TODAY)

    late.refresh_from_db()
    due_today.refresh_from_db()
    already_paid.refresh_from_db()
    assert late.status == Charge.Status.OVERDUE
    assert due_today.status == Charge.Status.PENDING
    assert already_paid.status == Charge.Status.PAID
    assert [d.charge_id for d in deliveries] == [late.pk]
    assert deliveries[0].event == WebhookDelivery.Event.OVERDUE


def test_mark_overdue_skips_webhook_when_charge_has_no_url(make_charge):
    charge = make_charge(due_date=date(2026, 10, 1), webhook_url="")

    deliveries = mark_overdue_charges(TODAY)

    charge.refresh_from_db()
    assert charge.status == Charge.Status.OVERDUE
    assert deliveries == []


def test_mark_overdue_twice_does_not_duplicate_notifications(make_charge):
    make_charge(due_date=date(2026, 10, 1))

    first = mark_overdue_charges(TODAY)
    second = mark_overdue_charges(TODAY)

    assert len(first) == 1
    assert second == []
    assert WebhookDelivery.objects.count() == 1


def test_pay_charge_creates_paid_notification(make_charge):
    charge = make_charge()

    delivery = pay_charge(charge)

    assert charge.status == Charge.Status.PAID
    assert delivery is not None
    assert delivery.event == WebhookDelivery.Event.PAID


def test_pay_charge_rejects_canceled_without_notification(make_charge):
    charge = make_charge(status=Charge.Status.CANCELED)

    with pytest.raises(ChargeStateError):
        pay_charge(charge)

    assert WebhookDelivery.objects.count() == 0
