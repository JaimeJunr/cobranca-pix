from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from charges.models import Charge


class IsChargeOwner(BasePermission):
    """Segunda trava: o queryset já filtra pelo dono, e esta checagem barra o acesso
    se alguém um dia trocar o queryset e esquecer o filtro."""

    def has_object_permission(self, request: Request, view: APIView | None, obj: Charge) -> bool:
        return obj.owner_id == request.user.id
