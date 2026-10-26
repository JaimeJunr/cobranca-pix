from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone
from rest_framework.authtoken.models import Token

from charges.models import Charge

DEMO_USERNAME = "demo"


class Command(BaseCommand):
    help = "Cria o usuário demo, o token da API e duas cobranças (uma já vencida)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--webhook-url", default="http://webhook-receiver:8001/hook")

    def handle(self, *args: object, webhook_url: str, **options: object) -> None:
        user, _created = User.objects.get_or_create(username=DEMO_USERNAME)
        token, _created = Token.objects.get_or_create(user=user)
        today = timezone.localdate()
        demo_charges = [
            ("Cliente Atrasado", Decimal("89.90"), today - timedelta(days=1)),
            ("Cliente em Dia", Decimal("120.00"), today + timedelta(days=10)),
        ]
        for payer_name, amount, due_date in demo_charges:
            Charge.objects.get_or_create(
                owner=user,
                payer_name=payer_name,
                defaults={
                    "amount": amount,
                    "description": "Cobrança de demonstração",
                    "payer_document": "12345678901",
                    "due_date": due_date,
                    "webhook_url": webhook_url,
                },
            )
        self.stdout.write(f"Token da API do usuário demo: {token.key}")
