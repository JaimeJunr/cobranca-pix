"""App do Celery. O worker e o beat sobem com `celery -A config worker|beat`."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("cobranca_pix")
# Lê as chaves CELERY_* do settings.py do Django.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
