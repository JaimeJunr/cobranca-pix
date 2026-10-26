"""Regras de negócio que mexem em mais de um model. Views e tarefas chamam daqui."""

from datetime import date

from django.db import transaction
from django.utils import timezone

from charges.models import Charge, WebhookDelivery


def mark_overdue_charges(today: date) -> list[WebhookDelivery]:
    with transaction.atomic():
        # skip_locked: se dois workers rodarem juntos, cada um pega linhas diferentes
        # em vez de um esperar o outro (no SQLite isso é ignorado).
        late_charges = list(
            Charge.objects.select_for_update(skip_locked=True).filter(
                status=Charge.Status.PENDING, due_date__lt=today
            )
        )
        Charge.objects.filter(pk__in=[charge.pk for charge in late_charges]).update(
            status=Charge.Status.OVERDUE, updated_at=timezone.now()
        )
        deliveries = [
            create_delivery(charge, WebhookDelivery.Event.OVERDUE) for charge in late_charges
        ]
    return [delivery for delivery in deliveries if delivery is not None]


@transaction.atomic
def pay_charge(charge: Charge) -> WebhookDelivery | None:
    charge.mark_paid()
    return create_delivery(charge, WebhookDelivery.Event.PAID)


def create_delivery(charge: Charge, event: str) -> WebhookDelivery | None:
    if not charge.webhook_url:
        return None
    delivery, _created = WebhookDelivery.objects.get_or_create(charge=charge, event=event)
    return delivery
