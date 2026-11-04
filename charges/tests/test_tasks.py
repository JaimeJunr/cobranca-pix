from datetime import date

import pytest

from charges.models import Charge, WebhookDelivery
from charges.tasks import mark_overdue_charges, retry_countdown, send_webhook
from charges.tests.fakes import network_error

pytestmark = pytest.mark.django_db


@pytest.fixture
def delivery(make_charge) -> WebhookDelivery:
    return WebhookDelivery.objects.create(charge=make_charge(), event=WebhookDelivery.Event.PAID)


def test_send_webhook_delivers_on_first_try(delivery, fake_sender):
    result = send_webhook.apply(args=[delivery.pk])

    delivery.refresh_from_db()
    assert result.successful()
    assert delivery.status == WebhookDelivery.Status.DELIVERED
    assert len(fake_sender.sent) == 1


def test_send_webhook_retries_until_receiver_recovers(delivery, fake_sender):
    fake_sender.responses = [500, network_error(), 200]

    send_webhook.apply(args=[delivery.pk])

    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.DELIVERED
    assert delivery.attempts == 3


def test_send_webhook_gives_up_after_max_retries(delivery, fake_sender, settings):
    fake_sender.responses = [500] * 20

    send_webhook.apply(args=[delivery.pk])

    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.FAILED
    assert delivery.attempts == send_webhook.max_retries + 1


def test_send_webhook_skips_already_delivered(delivery, fake_sender):
    delivery.status = WebhookDelivery.Status.DELIVERED
    delivery.save()

    send_webhook.apply(args=[delivery.pk])

    assert fake_sender.sent == []


def test_retry_countdown_grows_exponentially():
    assert [retry_countdown(n) for n in range(4)] == [10, 20, 40, 80]


def test_mark_overdue_task_notifies_each_late_charge(make_charge, fake_sender):
    charge = make_charge(due_date=date(2020, 1, 1))
    make_charge(due_date=date(2999, 1, 1))

    result = mark_overdue_charges.apply()

    charge.refresh_from_db()
    assert result.get() == 1
    assert charge.status == Charge.Status.OVERDUE
    assert len(fake_sender.sent) == 1
