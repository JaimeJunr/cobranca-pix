import pytest
from django.contrib.auth.models import User

from charges.models import WebhookDelivery

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    admin = User.objects.create_superuser("admin", "admin@example.com", "senha-forte-123")
    client.force_login(admin)
    return client


def test_charge_changelist_searches_by_payer(admin_client, make_charge):
    make_charge(payer_name="Carla Dias")
    make_charge(payer_name="Bruno Reis")

    response = admin_client.get("/admin/charges/charge/", {"q": "Carla"})

    assert response.status_code == 200
    assert b"Carla Dias" in response.content
    assert b"Bruno Reis" not in response.content


def test_charge_change_page_shows_deliveries_inline(admin_client, make_charge):
    charge = make_charge()
    WebhookDelivery.objects.create(charge=charge, event=WebhookDelivery.Event.PAID)

    response = admin_client.get(f"/admin/charges/charge/{charge.pk}/change/")

    assert response.status_code == 200
    assert b"charge.paid" in response.content


def test_resend_action_requeues_failed_deliveries(admin_client, make_charge, fake_sender):
    failed = WebhookDelivery.objects.create(
        charge=make_charge(),
        event=WebhookDelivery.Event.OVERDUE,
        status=WebhookDelivery.Status.FAILED,
        attempts=6,
    )

    response = admin_client.post(
        "/admin/charges/webhookdelivery/",
        {"action": "resend_webhooks", "_selected_action": [failed.pk]},
    )

    failed.refresh_from_db()
    assert response.status_code == 302
    assert failed.status == WebhookDelivery.Status.DELIVERED
    assert len(fake_sender.sent) == 1


def test_resend_action_ignores_delivered(admin_client, make_charge, fake_sender):
    delivered = WebhookDelivery.objects.create(
        charge=make_charge(),
        event=WebhookDelivery.Event.PAID,
        status=WebhookDelivery.Status.DELIVERED,
    )

    admin_client.post(
        "/admin/charges/webhookdelivery/",
        {"action": "resend_webhooks", "_selected_action": [delivered.pk]},
    )

    assert fake_sender.sent == []
