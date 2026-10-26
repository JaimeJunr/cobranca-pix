"""Tarefas do Celery. O beat agenda `mark_overdue_charges`; o worker executa as duas."""

from celery import Task, shared_task
from django.conf import settings
from django.utils import timezone

from charges import services
from charges.models import WebhookDelivery
from charges.webhooks import WebhookDeliveryError, deliver, get_webhook_sender

RETRY_BASE_SECONDS = 10


def retry_countdown(retries: int) -> int:
    # Espera 10s, 20s, 40s... para não martelar um cliente que está fora do ar.
    return RETRY_BASE_SECONDS * 2**retries


@shared_task
def mark_overdue_charges() -> int:
    deliveries = services.mark_overdue_charges(timezone.localdate())
    for delivery in deliveries:
        send_webhook.delay(delivery.pk)
    return len(deliveries)


@shared_task(bind=True, max_retries=settings.WEBHOOK_MAX_RETRIES)
def send_webhook(self: Task, delivery_id: int) -> str:
    delivery = WebhookDelivery.objects.select_related("charge").get(pk=delivery_id)
    if delivery.status != WebhookDelivery.Status.PENDING:
        return delivery.status
    try:
        deliver(delivery, get_webhook_sender())
    except WebhookDeliveryError as error:
        if self.request.retries >= self.max_retries:
            delivery.status = WebhookDelivery.Status.FAILED
            delivery.save(update_fields=["status"])
            return delivery.status
        raise self.retry(exc=error, countdown=retry_countdown(self.request.retries)) from error
    return delivery.status
