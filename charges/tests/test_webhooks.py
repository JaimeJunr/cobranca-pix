import hashlib
import hmac
import json

import pytest

from charges.models import WebhookDelivery
from charges.tests.fakes import network_error
from charges.webhooks import WebhookDeliveryError, deliver, sign

pytestmark = pytest.mark.django_db


@pytest.fixture
def delivery(make_charge) -> WebhookDelivery:
    return WebhookDelivery.objects.create(charge=make_charge(), event=WebhookDelivery.Event.OVERDUE)


def test_deliver_posts_signed_json_and_marks_delivered(delivery, fake_sender, settings):
    deliver(delivery, fake_sender)

    sent = fake_sender.sent[0]
    body = json.loads(sent.body)
    expected_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(), sent.body, hashlib.sha256
    ).hexdigest()
    assert sent.url == "https://hooks.example.com/pix"
    assert body["event"] == "charge.overdue"
    assert body["charge"]["txid"] == delivery.charge.txid
    assert body["charge"]["amount"] == "150.50"
    assert sent.headers["X-Signature-SHA256"] == expected_signature
    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.DELIVERED
    assert delivery.attempts == 1
    assert delivery.response_status == 200


def test_deliver_raises_and_records_non_2xx_response(delivery, fake_sender):
    fake_sender.responses = [503]

    with pytest.raises(WebhookDeliveryError, match="503"):
        deliver(delivery, fake_sender)

    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.PENDING
    assert delivery.attempts == 1
    assert delivery.response_status == 503
    assert "503" in delivery.last_error


def test_deliver_records_network_error(delivery, fake_sender):
    fake_sender.responses = [network_error()]

    with pytest.raises(WebhookDeliveryError, match="connection refused"):
        deliver(delivery, fake_sender)

    delivery.refresh_from_db()
    assert delivery.response_status is None
    assert delivery.last_error == "connection refused"


def test_sign_is_stable_and_depends_on_secret():
    assert sign(b"{}", "a") == sign(b"{}", "a")
    assert sign(b"{}", "a") != sign(b"{}", "b")
