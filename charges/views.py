from django.db import connection, transaction
from django.db.models import QuerySet
from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from charges import services
from charges.documents import render_charge_pdf, render_qrcode_svg
from charges.models import Charge, ChargeStateError
from charges.permissions import IsChargeOwner
from charges.serializers import ChargeSerializer
from charges.tasks import send_webhook


class ChargeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Cobrança não é apagada nem editada: muda de estado só por pay e cancel."""

    serializer_class = ChargeSerializer
    permission_classes = [IsAuthenticated, IsChargeOwner]

    def get_queryset(self) -> QuerySet[Charge]:
        queryset = Charge.objects.filter(owner=self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def perform_create(self, serializer: ChargeSerializer) -> None:
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def pay(self, request: Request, pk: str | None = None) -> Response:
        """Simula a confirmação do banco. Num sistema real quem chama isto é o
        webhook do provedor Pix, não o próprio lojista."""
        charge = self.get_object()
        try:
            delivery = services.pay_charge(charge)
        except ChargeStateError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        if delivery is not None:
            # Só enfileira depois do COMMIT: senão o worker pode buscar a entrega
            # antes de ela existir no banco.
            transaction.on_commit(lambda: send_webhook.delay(delivery.pk))
        return Response(self.get_serializer(charge).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        charge = self.get_object()
        try:
            charge.cancel()
        except ChargeStateError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(charge).data)

    @action(detail=True, methods=["get"])
    def qrcode(self, request: Request, pk: str | None = None) -> HttpResponse:
        return HttpResponse(render_qrcode_svg(self.get_object()), content_type="image/svg+xml")

    @action(detail=True, methods=["get"])
    def pdf(self, request: Request, pk: str | None = None) -> HttpResponse:
        charge = self.get_object()
        response = HttpResponse(render_charge_pdf(charge), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="cobranca-{charge.txid}.pdf"'
        return response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    connection.ensure_connection()
    return Response({"status": "ok"})
