"""Settings de desenvolvimento.

Banco PostgreSQL via docker-compose (AP-13 — nunca SQLite). DEBUG ligado.
Email no console. Bloco de seguranca/HSTS fica apenas em prod.
"""

from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ['*']

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
