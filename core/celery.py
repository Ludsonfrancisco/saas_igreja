"""Celery bootstrap (OD-003 / A3 — Celery + Redis desde a Sprint 1).

Tasks pesadas (importacao CSV, purge LGPD semanal, emails) serao registradas
nas apps a partir das sprints correspondentes. Aqui fica apenas o app base com
autodiscovery; nenhuma task e definida neste bloco de scaffold.
"""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.dev')

app = Celery('core')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
