"""Envio de webhook: avisa o sistema do cliente quando uma cobrança muda de estado."""

import hashlib
import hmac
import json
from typing import Protocol

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

from charges.models import WebhookDelivery


class WebhookDeliveryError(Exception):
    pass


class WebhookSender(Protocol):
    def post(self, url: str, body: bytes, headers: dict[str, str]) -> int: ...


class HttpWebhookSender:
    def __init__(self, timeout_seconds: float | None = None) -> None:
        self.timeout_seconds = timeout_seconds or settings.WEBHOOK_TIMEOUT_SECONDS

    def post(self, url: str, body: bytes, headers: dict[str, str]) -> int:
        try:
            response = requests.post(url, data=body, headers=headers, timeout=self.timeout_seconds)
        except requests.RequestException as error:
            raise WebhookDeliveryError(str(error)) from error
        return response.status_code


def get_webhook_sender() -> WebhookSender:
    return import_string(settings.WEBHOOK_SENDER_FACTORY)()


def sign(body: bytes, secret: str) -> str:
    # O cliente recalcula o HMAC com o mesmo segredo para saber que o aviso veio de nós.
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def build_body(delivery: WebhookDelivery) -> bytes:
    charge = delivery.charge
    payload = {
        "event": delivery.event,
        "delivery_id": delivery.pk,
        "charge": {
            "txid": charge.txid,
            "amount": str(charge.amount),
            "status": charge.status,
            "due_date": charge.due_date.isoformat(),
            "paid_at": charge.paid_at.isoformat() if charge.paid_at else None,
        },
    }
    return json.dumps(payload, separators=(",", ":")).encode()


def deliver(delivery: WebhookDelivery, sender: WebhookSender) -> None:
    body = build_body(delivery)
    headers = {
        "Content-Type": "application/json",
        "X-Signature-SHA256": sign(body, settings.WEBHOOK_SECRET),
    }
    delivery.attempts += 1
    try:
        status_code = sender.post(delivery.charge.webhook_url, body, headers)
    except WebhookDeliveryError as error:
        _record_failure(delivery, response_status=None, error=str(error))
        raise

    if not 200 <= status_code < 300:
        error = f"receiver answered HTTP {status_code}, expected 2xx"
        _record_failure(delivery, response_status=status_code, error=error)
        raise WebhookDeliveryError(error)

    delivery.status = WebhookDelivery.Status.DELIVERED
    delivery.response_status = status_code
    delivery.last_error = ""
    delivery.delivered_at = timezone.now()
    delivery.save()


def _record_failure(delivery: WebhookDelivery, *, response_status: int | None, error: str) -> None:
    delivery.response_status = response_status
    delivery.last_error = error
    delivery.save(update_fields=["attempts", "response_status", "last_error"])
