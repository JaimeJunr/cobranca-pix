import secrets
import string
from datetime import date

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from charges.pix import build_static_payload

TXID_ALPHABET = string.ascii_uppercase + string.digits


def generate_txid() -> str:
    # 25 caracteres é o máximo que o campo txid do BR Code aceita.
    return "".join(secrets.choice(TXID_ALPHABET) for _ in range(25))


class ChargeStateError(Exception):
    pass


class Charge(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        PAID = "paid", "Paga"
        OVERDUE = "overdue", "Vencida"
        CANCELED = "canceled", "Cancelada"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="charges"
    )
    txid = models.CharField(max_length=25, unique=True, default=generate_txid, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=140)
    payer_name = models.CharField(max_length=120)
    payer_document = models.CharField(
        max_length=14,
        validators=[RegexValidator(r"^(\d{11}|\d{14})$", "Informe CPF ou CNPJ só com dígitos.")],
    )
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    webhook_url = models.URLField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="charge_amount_positive"),
        ]
        indexes = [
            # Listagem da API: sempre filtra pelo dono e ordena pela data de criação.
            models.Index(fields=["owner", "-created_at"], name="charge_owner_created_idx"),
            # Índice parcial: o job de vencidas só olha as pendentes, que são poucas
            # perto do histórico de pagas; o índice fica pequeno e a busca, rápida.
            models.Index(
                fields=["due_date"],
                condition=Q(status="pending"),
                name="charge_pending_due_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.txid} · {self.payer_name} · R$ {self.amount}"

    def pix_payload(self) -> str:
        return build_static_payload(
            key=settings.PIX_KEY,
            merchant_name=settings.PIX_MERCHANT_NAME,
            merchant_city=settings.PIX_MERCHANT_CITY,
            amount=self.amount,
            txid=self.txid,
        )

    def is_overdue_on(self, day: date) -> bool:
        return self.due_date < day

    def mark_paid(self) -> None:
        self._require_status({self.Status.PENDING, self.Status.OVERDUE}, action="pay")
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at", "updated_at"])

    def cancel(self) -> None:
        self._require_status({self.Status.PENDING, self.Status.OVERDUE}, action="cancel")
        self.status = self.Status.CANCELED
        self.save(update_fields=["status", "updated_at"])

    def _require_status(self, allowed: set[str], *, action: str) -> None:
        if self.status not in allowed:
            raise ChargeStateError(
                f"cannot {action} charge {self.txid}: received status {str(self.status)!r}, "
                f"expected one of {sorted(str(status) for status in allowed)}"
            )


class WebhookDelivery(models.Model):
    class Event(models.TextChoices):
        PAID = "charge.paid", "Cobrança paga"
        OVERDUE = "charge.overdue", "Cobrança vencida"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        DELIVERED = "delivered", "Entregue"
        FAILED = "failed", "Falhou"

    charge = models.ForeignKey(Charge, on_delete=models.CASCADE, related_name="deliveries")
    event = models.CharField(max_length=20, choices=Event.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    response_status = models.PositiveIntegerField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Um evento por cobrança: se o job rodar duas vezes, não notifica em dobro.
            models.UniqueConstraint(fields=["charge", "event"], name="delivery_unique_event"),
        ]

    def __str__(self) -> str:
        return f"{self.event} · {self.charge.txid} · {self.status}"
