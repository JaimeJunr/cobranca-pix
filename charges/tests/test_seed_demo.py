import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.authtoken.models import Token

from charges.models import Charge

pytestmark = pytest.mark.django_db


def test_seed_demo_creates_user_token_and_one_overdue_candidate(capsys):
    call_command("seed_demo", webhook_url="http://receiver:8001/hook")

    user = User.objects.get(username="demo")
    token = Token.objects.get(user=user)
    assert token.key in capsys.readouterr().out
    late = Charge.objects.get(owner=user, payer_name="Cliente Atrasado")
    assert late.webhook_url == "http://receiver:8001/hook"
    assert late.status == Charge.Status.PENDING


def test_seed_demo_is_idempotent():
    call_command("seed_demo", webhook_url="http://receiver:8001/hook")
    call_command("seed_demo", webhook_url="http://receiver:8001/hook")

    assert User.objects.filter(username="demo").count() == 1
    assert Charge.objects.filter(owner__username="demo").count() == 2
