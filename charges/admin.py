from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest

from charges.models import Charge, WebhookDelivery
from charges.tasks import send_webhook


class WebhookDeliveryInline(admin.TabularInline):
    model = WebhookDelivery
    extra = 0
    can_delete = False
    fields = ["event", "status", "attempts", "response_status", "last_error", "delivered_at"]
    readonly_fields = fields


@admin.register(Charge)
class ChargeAdmin(admin.ModelAdmin):
    list_display = ["txid", "payer_name", "amount", "due_date", "status", "owner", "created_at"]
    list_filter = ["status", "due_date"]
    search_fields = ["txid", "payer_name", "payer_document"]
    readonly_fields = ["txid", "paid_at", "created_at", "updated_at"]
    date_hierarchy = "due_date"
    list_select_related = ["owner"]
    inlines = [WebhookDeliveryInline]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ["charge", "event", "status", "attempts", "response_status", "created_at"]
    list_filter = ["status", "event"]
    search_fields = ["charge__txid"]
    readonly_fields = ["attempts", "response_status", "last_error", "delivered_at"]
    list_select_related = ["charge"]
    actions = ["resend_webhooks"]

    @admin.action(description="Reenviar webhooks que falharam")
    def resend_webhooks(self, request: HttpRequest, queryset: QuerySet[WebhookDelivery]) -> None:
        failed = list(queryset.filter(status=WebhookDelivery.Status.FAILED))
        for delivery in failed:
            delivery.status = WebhookDelivery.Status.PENDING
            delivery.save(update_fields=["status"])
            send_webhook.delay(delivery.pk)
        self.message_user(request, f"{len(failed)} webhook(s) reenfileirado(s).", messages.SUCCESS)
