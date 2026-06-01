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

# --- Apps ---
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# Bounded contexts (P-ARQ-01). Apps vazias neste bloco de scaffold; models
# entram nos blocos "Models de fundação" e seguintes.
LOCAL_APPS = [
    'apps.core',
    'apps.accounts',
    'apps.tenants',
    'apps.people',
    'apps.communities',
    'apps.ministries',
    'apps.gatherings',
    'apps.schedules',
    'apps.files',
    'apps.dashboard',
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

# django-tenants (SHARED_APPS/TENANT_APPS/DATABASE_ROUTERS) — bloco
# 'Models de fundação' / 'Multi-tenancy'. Nao configurar aqui ainda.

MIDDLEWARE = [
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
        'ENGINE': 'django.db.backends.postgresql',
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
# AUTH_USER_MODEL = 'accounts.User'  # definido no bloco Models de fundação (Sprint 1)
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
