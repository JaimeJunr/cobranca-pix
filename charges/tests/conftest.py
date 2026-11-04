from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from charges.models import Charge
from charges.tests.fakes import FakeWebhookSender, install_fake_sender
from config.celery import app as celery_app


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(username="loja", password="senha-forte-123")


@pytest.fixture
def other_owner(db) -> User:
    return User.objects.create_user(username="concorrente", password="senha-forte-123")


@pytest.fixture
def make_charge(owner):
    def factory(**overrides) -> Charge:
        fields = {
            "owner": owner,
            "amount": Decimal("150.50"),
            "description": "Mensalidade outubro",
            "payer_name": "Maria Souza",
            "payer_document": "12345678901",
            "due_date": date.today() + timedelta(days=5),
            "webhook_url": "https://hooks.example.com/pix",
        }
        fields.update(overrides)
        return Charge.objects.create(**fields)

    return factory


@pytest.fixture
def api_client(owner) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.fixture(autouse=True)
def fake_sender(settings) -> FakeWebhookSender:
    # Nenhum teste faz HTTP de verdade: o enviador é sempre o fake em memória.
    sender = FakeWebhookSender()
    install_fake_sender(sender)
    settings.WEBHOOK_SENDER_FACTORY = "charges.tests.fakes.current_fake_sender"
    return sender


@pytest.fixture(autouse=True)
def celery_eager():
    # Executa a tarefa na hora, no mesmo processo, sem precisar de RabbitMQ.
    # A chave vai com o prefixo CELERY_ porque o app lê o settings com namespace="CELERY".
    celery_app.conf.update(CELERY_TASK_ALWAYS_EAGER=True)
    yield
    celery_app.conf.update(CELERY_TASK_ALWAYS_EAGER=False)
