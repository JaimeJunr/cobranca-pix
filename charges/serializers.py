from datetime import date
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from charges.models import Charge


class ChargeSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    pix_copia_e_cola = serializers.SerializerMethodField()

    class Meta:
        model = Charge
        fields = [
            "id",
            "txid",
            "amount",
            "description",
            "payer_name",
            "payer_document",
            "due_date",
            "status",
            "webhook_url",
            "pix_copia_e_cola",
            "paid_at",
            "created_at",
        ]
        # O cliente não escolhe status nem txid: eles só mudam pelas ações pay/cancel.
        read_only_fields = ["id", "txid", "status", "paid_at", "created_at"]

    def get_pix_copia_e_cola(self, charge: Charge) -> str:
        return charge.pix_payload()

    def validate_due_date(self, value: date) -> date:
        today = timezone.localdate()
        if value < today:
            raise serializers.ValidationError(
                f"received {value.isoformat()}, expected today ({today.isoformat()}) or later"
            )
        return value
