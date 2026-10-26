from datetime import date, timedelta

import pytest
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from charges.models import Charge, WebhookDelivery

pytestmark = pytest.mark.django_db

VALID_BODY = {
    "amount": "250.00",
    "description": "Plano anual",
    "payer_name": "João Lima",
    "payer_document": "12345678000199",
    "due_date": (date.today() + timedelta(days=3)).isoformat(),
    "webhook_url": "https://hooks.example.com/pix",
}


def test_create_charge_returns_pix_copy_paste(api_client, owner):
    response = api_client.post("/api/charges/", VALID_BODY, format="json")

    assert response.status_code == 201
    charge = Charge.objects.get(pk=response.data["id"])
    assert charge.owner == owner
    assert response.data["status"] == "pending"
    assert response.data["pix_copia_e_cola"] == charge.pix_payload()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount", "0"),
        ("payer_document", "123"),
        ("due_date", (date.today() - timedelta(days=1)).isoformat()),
    ],
)
def test_create_charge_rejects_invalid_field(api_client, field, value):
    response = api_client.post("/api/charges/", {**VALID_BODY, field: value}, format="json")

    assert response.status_code == 400
    assert field in response.data


def test_client_cannot_set_status_on_create(api_client):
    response = api_client.post("/api/charges/", {**VALID_BODY, "status": "paid"}, format="json")

    assert response.status_code == 201
    assert response.data["status"] == "pending"


def test_anonymous_request_is_rejected():
    response = APIClient().get("/api/charges/")

    assert response.status_code == 401


def test_token_authentication_works(owner):
    token = Token.objects.create(user=owner)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    assert client.get("/api/charges/").status_code == 200


def test_obtain_token_with_username_and_password(owner):
    response = APIClient().post(
        "/api/token/", {"username": "loja", "password": "senha-forte-123"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["token"]


def test_list_shows_only_own_charges_and_filters_by_status(api_client, make_charge, other_owner):
    mine_pending = make_charge()
    make_charge(status=Charge.Status.PAID)
    make_charge(owner=other_owner)

    response = api_client.get("/api/charges/", {"status": "pending"})

    assert response.status_code == 200
    assert [item["id"] for item in response.data["results"]] == [mine_pending.pk]


def test_other_owners_charge_is_not_found(api_client, make_charge, other_owner):
    foreign = make_charge(owner=other_owner)

    assert api_client.get(f"/api/charges/{foreign.pk}/").status_code == 404
    assert api_client.post(f"/api/charges/{foreign.pk}/pay/").status_code == 404


def test_pay_marks_paid_and_sends_webhook(
    api_client, make_charge, fake_sender, django_capture_on_commit_callbacks
):
    charge = make_charge()

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(f"/api/charges/{charge.pk}/pay/")

    assert response.status_code == 200
    assert response.data["status"] == "paid"
    delivery = WebhookDelivery.objects.get(charge=charge)
    assert delivery.event == "charge.paid"
    assert delivery.status == WebhookDelivery.Status.DELIVERED
    assert len(fake_sender.sent) == 1


def test_pay_canceled_charge_returns_conflict(api_client, make_charge):
    charge = make_charge(status=Charge.Status.CANCELED)

    response = api_client.post(f"/api/charges/{charge.pk}/pay/")

    assert response.status_code == 409
    assert "canceled" in response.data["detail"]


def test_cancel_pending_charge(api_client, make_charge):
    charge = make_charge()

    response = api_client.post(f"/api/charges/{charge.pk}/cancel/")

    assert response.status_code == 200
    assert response.data["status"] == "canceled"


def test_cancel_paid_charge_returns_conflict(api_client, make_charge):
    charge = make_charge(status=Charge.Status.PAID)

    assert api_client.post(f"/api/charges/{charge.pk}/cancel/").status_code == 409


def test_qrcode_returns_svg(api_client, make_charge):
    charge = make_charge()

    response = api_client.get(f"/api/charges/{charge.pk}/qrcode/")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/svg+xml"
    assert b"<svg" in response.content


def test_pdf_returns_document_named_after_txid(api_client, make_charge):
    charge = make_charge()

    response = api_client.get(f"/api/charges/{charge.pk}/pdf/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert charge.txid in response["Content-Disposition"]
    assert response.content.startswith(b"%PDF")


def test_charges_cannot_be_deleted(api_client, make_charge):
    charge = make_charge()

    assert api_client.delete(f"/api/charges/{charge.pk}/").status_code == 405


def test_health_is_public():
    response = APIClient().get("/api/health/")

    assert response.status_code == 200
    assert response.data == {"status": "ok"}
