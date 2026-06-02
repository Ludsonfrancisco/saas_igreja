"""Settings comuns a todos os ambientes.

Secrets e configuracao sensivel vem sempre de variaveis de ambiente via
python-decouple (SEC-06 / AP-12). Nenhum secret hardcoded.
Banco e sempre PostgreSQL (AP-13 — SQLite proibido com django-tenants).
"""

from pathlib import Path
from urllib.parse import urlparse

from decouple import Csv, config

# core/settings/base.py -> sobe 3 niveis ate a raiz do projeto.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Seguranca base (SEC-06 / AP-12) ---
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=Csv())

# --- Apps (django-tenants: schema-per-tenant) ---
# SHARED_APPS vivem no schema `public`; TENANT_APPS migram para cada schema de
# tenant. django_tenants precisa ser o primeiro. Church/Domain/Plan (tenants) e
# User/Invite/PlatformAdmin/SupportAccess (accounts) sao models PUBLICOS
# (TENANT-04). apps.core fica em TENANT_APPS para que AuditLog/SecurityLog
# (Sprint 2) migrem para cada schema de tenant (TECH_SPEC §5.9.1).
SHARED_APPS = [
    'django_tenants',
    'apps.tenants',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.accounts',
]

# Bounded contexts tenant-scoped (P-ARQ-01).
TENANT_APPS = [
    'apps.core',
    'apps.people',
    'apps.communities',
    'apps.ministries',
    'apps.gatherings',
    'apps.schedules',
    'apps.files',
    'apps.dashboard',
]

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

# django-tenants core config (TECH_SPEC §5.9.1 / §4).
TENANT_MODEL = 'tenants.Church'
TENANT_DOMAIN_MODEL = 'tenants.Domain'
DATABASE_ROUTERS = ('django_tenants.routers.TenantSyncRouter',)

# django-tenants exige o middleware de tenant no TOPO da cadeia: ele resolve o
# subdominio -> schema antes de qualquer outro middleware tocar o request
# (TECH_SPEC §4.3 / TENANT-05). Em dev, tenants sao acessados via
# `<slug>.localhost:8000` e a area publica/landing via `localhost:8000`
# (resolvers modernos mapeiam *.localhost -> 127.0.0.1; ALLOWED_HOSTS ja cobre
# `.localhost`).
MIDDLEWARE = [
    'apps.tenants.middleware.TenantMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# --- Banco de dados (PostgreSQL 15+ — AP-13) ---
# DATABASE_URL e parseada manualmente (dj-database-url nao esta nas deps).
# Formato esperado: postgres://user:password@host:port/dbname
_db = urlparse(config('DATABASE_URL'))
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': _db.path.lstrip('/'),
        'USER': _db.username or '',
        'PASSWORD': _db.password or '',
        'HOST': _db.hostname or '',
        'PORT': str(_db.port or ''),
    }
}

# --- Redis (broker Celery + readiness check — OD-003) ---
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# --- Auth ---
AUTH_USER_MODEL = 'accounts.User'

# EmailBackend primeiro (login por email); ModelBackend como fallback para
# admin/superuser (P-ARQ-03 / SEC-02).
AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

_PASSWORD_VALIDATION = 'django.contrib.auth.password_validation'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': f'{_PASSWORD_VALIDATION}.UserAttributeSimilarityValidator'},
    {'NAME': f'{_PASSWORD_VALIDATION}.MinimumLengthValidator'},
    {'NAME': f'{_PASSWORD_VALIDATION}.CommonPasswordValidator'},
    {'NAME': f'{_PASSWORD_VALIDATION}.NumericPasswordValidator'},
]

# --- Internacionalizacao (interface 100% pt-BR) ---
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# --- Arquivos estaticos e de midia ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
