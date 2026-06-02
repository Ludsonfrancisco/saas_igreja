"""Settings de desenvolvimento.

Banco PostgreSQL via docker-compose (AP-13 — nunca SQLite). DEBUG ligado.
Email no console. Bloco de seguranca/HSTS fica apenas em prod.

Ferramentas de performance baseline (Sprint 1) vivem SO aqui, nunca em
base.py nem prod.py:
  - nplusone           : levanta NPlusOneError em qualquer N+1 (P-ARQ-09).
  - django-debug-toolbar: inspeciona queries/perf no navegador (dev-only).
"""

from django.conf import settings as django_settings

from .base import *  # noqa: F401,F403
from .base import INSTALLED_APPS, MIDDLEWARE

DEBUG = True

ALLOWED_HOSTS = ['*']

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# --- Performance baseline (dev only) ---
# nplusone nao tem models, entao nao ha migracao/tenant a considerar.
INSTALLED_APPS = INSTALLED_APPS + [
    'nplusone.ext.django',
    'debug_toolbar',
]

# TenantMiddleware PRECISA continuar em primeiro (resolve subdominio -> schema
# antes de tudo). Reconstruimos a cadeia a partir do base e inserimos as
# ferramentas de dev logo apos ele:
#   1. debug_toolbar : o mais cedo possivel, porem apos middlewares que
#      codificam a resposta — aqui, logo depois do TenantMiddleware.
#   2. nplusone      : alto na cadeia para capturar queries de toda a request.
_tenant_mw = 'apps.tenants.middleware.TenantMiddleware'
_rest = [mw for mw in MIDDLEWARE if mw != _tenant_mw]
MIDDLEWARE = [
    _tenant_mw,
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'nplusone.ext.django.NPlusOneMiddleware',
    *_rest,
]

# P-ARQ-09 / RNF-024: qualquer N+1 deve quebrar (raise NPlusOneError), nao
# apenas logar. Assim os testes falham diante de regressao de N+1.
NPLUSONE_RAISE = True

# django-debug-toolbar (dev only).
INTERNAL_IPS = ['127.0.0.1', 'localhost']

# Sob Docker / IPs variados em dev, INTERNAL_IPS pode nao casar; o callback
# libera a toolbar sempre que DEBUG estiver ligado. CRITICO: ler
# `django_settings.DEBUG` em tempo de request (nao a global `DEBUG` do modulo)
# — assim, sob o test runner (que forca settings.DEBUG=False) o callback
# devolve False e a toolbar fica realmente inerte, sem estourar NoReverseMatch.
DEBUG_TOOLBAR_CONFIG = {'SHOW_TOOLBAR_CALLBACK': lambda request: django_settings.DEBUG}
