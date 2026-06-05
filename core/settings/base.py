"""Settings comuns a todos os ambientes.

Secrets e configuracao sensivel vem sempre de variaveis de ambiente via
python-decouple (SEC-06 / AP-12). Nenhum secret hardcoded.
Banco e sempre PostgreSQL (AP-13 — SQLite proibido com django-tenants).
"""

from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from celery.schedules import crontab
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
    # django.contrib.sites: exigido pelo allauth (FK SocialApp -> Site e
    # resolucao de dominio nos emails). SITE_ID=1 abaixo. Vive no public porque
    # Site/SocialApp sao globais da plataforma, nao por-tenant.
    'django.contrib.sites',
    # allauth: login por email (SEC-02 / P-ARQ-03). Os models do allauth
    # (EmailAddress, EmailConfirmation, etc.) referenciam User, que e PUBLICO
    # (TENANT-04) -> allauth fica em SHARED_APPS (schema public), NUNCA em
    # TENANT_APPS. allauth.account.middleware.AccountMiddleware abaixo.
    'allauth',
    'allauth.account',
    # allauth.mfa: MFA TOTP opt-in (RF-018a / OD-002 / PRD §15.4). O model
    # Authenticator referencia o User PUBLICO (TENANT-04) -> SHARED_APPS, junto
    # com allauth.account. Traz suas proprias migracoes (migrate_schemas
    # --shared). Enforcement obrigatorio p/ pastor/PlatformAdmin e Sprint 7.
    'allauth.mfa',
    # axes: account lockout / brute force (SEC-02). O lockout e contra o User
    # publico (login por email), entao seus models (AccessAttempt/AccessLog)
    # tambem vivem no public -> SHARED_APPS.
    'axes',
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
    # AccountMiddleware do allauth 65+ e OBRIGATORIO e deve vir DEPOIS de
    # AuthenticationMiddleware (precisa de request.user). Mantem invariantes de
    # sessao/redirect do allauth.
    'allauth.account.middleware.AccountMiddleware',
    # AuditContextMiddleware precisa de request.user (depois de
    # AuthenticationMiddleware) e do schema ja resolvido (depois de
    # TenantMiddleware, mantido no topo). Carrega user_id+IP no thread-local
    # lido pelos signals de auditoria (TECH_SPEC §2 / §5.9).
    'apps.core.middleware.AuditContextMiddleware',
    # PlatformAdminSupportMiddleware (RN-015 / RISK-009) vem DEPOIS de
    # AuditContextMiddleware: precisa de request.user (AuthenticationMiddleware),
    # request.tenant e do schema ja resolvido (TenantMiddleware, no topo). Bloqueia
    # qualquer request de Platform Admin a um tenant sem SupportAccess ativo e
    # audita cada acesso/negacao no SecurityLog do tenant.
    'apps.core.middleware.PlatformAdminSupportMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # AxesMiddleware deve vir DEPOIS de AuthenticationMiddleware: intercepta o
    # request quando o usuario/IP esta bloqueado e dispara o handler de lockout.
    # Fica por ultimo na cadeia (recomendacao do axes).
    'axes.middleware.AxesMiddleware',
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
                # Tema visual da igreja atual (Sprint 6.5 / DS-01) — injeta
                # accent/hot/logo da Church em CSS vars no base.html.
                'apps.core.context_processors.church_theme',
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
# Casa com TIME_ZONE (definido adiante); literal para evitar forward-reference.
CELERY_TIMEZONE = 'America/Sao_Paulo'

# Celery Beat (schedule estático — sem django-celery-beat/DB). RN-006: purge físico
# semanal do soft delete LGPD. Segunda-feira 04:00 (horário de baixa carga).
CELERY_BEAT_SCHEDULE = {
    'purge-anonymized-persons-weekly': {
        'task': 'apps.people.tasks.purge_anonymized_persons',
        'schedule': crontab(hour=4, minute=0, day_of_week='monday'),
    },
}

# --- Auth ---
AUTH_USER_MODEL = 'accounts.User'

# Ordem dos backends (SEC-02). CRITICO:
#   1. AxesStandaloneBackend PRIMEIRO: barra a tentativa ANTES de qualquer
#      backend de credencial quando o usuario/IP esta bloqueado (axes 7+/8
#      exige o StandaloneBackend no topo quando ja se usam backends proprios).
#   2. EmailBackend: nosso login por email case-insensitive (mitiga timing).
#   3. allauth.account.auth_backends.AuthenticationBackend: necessario para os
#      fluxos do allauth (reset/confirm). Como nosso USERNAME_FIELD ja e email,
#      EmailBackend resolve o login normal; o allauth backend cobre os fluxos
#      proprios sem quebrar o login existente.
#   4. ModelBackend: fallback para admin/superuser.
# axes encadeia os backends seguintes: se nao estiver bloqueado, o proximo
# backend autentica normalmente.
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'apps.accounts.backends.EmailBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# --- django.contrib.sites / allauth (SEC-02 / PRD §15.1) ---
SITE_ID = 1

# Login por email apenas (sem username). Nomenclatura ATUAL do allauth 65+:
# LOGIN_METHODS / SIGNUP_FIELDS substituem ACCOUNT_AUTHENTICATION_METHOD /
# ACCOUNT_EMAIL_REQUIRED / ACCOUNT_USERNAME_REQUIRED (deprecados).
ACCOUNT_LOGIN_METHODS = {'email'}
# email obrigatorio; sem campo username; senha + confirmacao no formulario.
# (O cadastro publico esta FECHADO via AccountAdapter.is_open_for_signup -> False;
#  SIGNUP_FIELDS so descreve o shape do form caso o signup fosse aberto, alem de
#  ser usado pelo fluxo de aceite de convite na Frente 4.)
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
# Sem verificacao de email no MVP: usuarios entram por convite (email ja
# confiavel). Evita travar login atras de confirmacao (OD-004/Frente 4).
ACCOUNT_EMAIL_VERIFICATION = 'none'
# Adapter customizado: fecha o signup e audita o pedido de reset de senha.
ACCOUNT_ADAPTER = 'apps.accounts.adapter.AccountAdapter'
# Mantemos o EmailBackend customizado como caminho de login; informamos ao
# allauth para preserva-lo na cadeia de rate limiting/erros.
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False

# Destino de redirect para nao-autenticado (usado por LoginRequiredMixin /
# TenantRequiredMixin) e pos-login/logout. Aponta para a rota NOMEADA do allauth
# (`account_login`, sob o prefixo `contas/`) resolvida via reverse() — em vez do
# default do Django (`/accounts/login/`, rota inexistente neste projeto). Usar o
# nome (e nao o caminho cravado) mantem isto correto se o prefixo `contas/` mudar.
LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'account_login'

# Remetente padrao dos emails transacionais (convites, reset de senha). Em dev
# vai para o console; em prod, via Brevo/anymail (ver prod.py). Fallback aqui
# garante um remetente valido mesmo sem env var configurada (Frente 4 / OD-012).
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='nao-responda@saasigreja.com')

# --- django-axes (SEC-02): 5 falhas -> lockout 15 min ---
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
# Bloqueia pela combinacao usuario+IP: evita que um atacante em um IP bloqueie a
# conta de outra pessoa globalmente, e ao mesmo tempo limita brute force por IP.
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
# Resetar contador de falhas apos um login bem-sucedido.
AXES_RESET_ON_SUCCESS = True
# axes precisa saber o nome do campo de credencial (email, nao username). O
# formulario do allauth posta como `login`; mantemos por consistencia.
AXES_USERNAME_FORM_FIELD = 'login'
# Callable que resolve o username a partir de credentials OU request.POST,
# cobrindo a divergencia de chaves entre o form do allauth (`login`) e os
# `credentials` do signal user_login_failed (`email`/`username`). Sem isso o
# axes registra username=None e o lockout degrada para somente-IP.
AXES_USERNAME_CALLABLE = 'apps.accounts.axes_helpers.get_username'

_PASSWORD_VALIDATION = 'django.contrib.auth.password_validation'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': f'{_PASSWORD_VALIDATION}.UserAttributeSimilarityValidator'},
    {'NAME': f'{_PASSWORD_VALIDATION}.MinimumLengthValidator'},
    {'NAME': f'{_PASSWORD_VALIDATION}.CommonPasswordValidator'},
    {'NAME': f'{_PASSWORD_VALIDATION}.NumericPasswordValidator'},
    # Politica do projeto (SEC-02 / PRD §15.1): 8+ chars, 1 numero, 1 especial,
    # e diferente/sem conter email ou nome. Mensagens em pt-BR.
    {
        'NAME': 'apps.accounts.validators.PasswordPolicyValidator',
        'OPTIONS': {'min_length': 8},
    },
]

# Token de reset de senha expira em 24h (PRD §15.1). Valor em SEGUNDOS; aplica-se
# ao token de reset do Django/allauth (default Django e 3 dias).
PASSWORD_RESET_TIMEOUT = 86400

# --- MFA opt-in (allauth.mfa / RF-018a / OD-002 / PRD §15.4) ---
# Sprint 2: qualquer usuario pode habilitar MFA TOTP na propria conta. O
# enforcement obrigatorio (pastor/PlatformAdmin) e Sprint 7 (RF-018b).
#
# So TOTP + recovery codes no MVP (sem WebAuthn). Os recovery codes sao os "8
# backup codes de uso unico" do SPRINTS §186 — single-use ja e nativo; aqui so
# fixamos a contagem em 8 (default do allauth e 10).
MFA_SUPPORTED_TYPES = ['totp', 'recovery_codes']
MFA_RECOVERY_CODE_COUNT = 8
# Emissor exibido no app autenticador (rotulo do QR code).
MFA_TOTP_ISSUER = 'SaaS Igreja'

# --- Internacionalizacao (interface 100% pt-BR) ---
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# --- Arquivos estaticos e de midia ---
# Storage de midia (Sprint 6 / OD-003a / OD-007 / RNF-018 / RISK-005):
#   - dev/teste : FileSystemStorage local (MEDIA_ROOT abaixo). Sem dependencia
#                 de R2 real — a suite e o `runserver` funcionam offline.
#   - prod      : Cloudflare R2 (S3-compatible) via django-storages. A
#                 configuracao do backend S3 vive em prod.py (STORAGES['default']),
#                 com credenciais por env var (python-decouple, SEC-06 / AP-12).
# Django 5.2 usa a API STORAGES (dict 'default' + 'staticfiles'); o antigo
# DEFAULT_FILE_STORAGE/STATICFILES_STORAGE esta DEPRECADO e NAO e usado aqui.
# O caminho logico do objeto e identico nos dois backends (apps.core.storage
# .tenant_upload_path -> {tenant_schema}/{model}/{object_id}/{filename}); so o
# backend muda por ambiente.
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = 'media/'
# Default de dev/teste; prod.py mantem MEDIA_ROOT irrelevante (backend e R2).
MEDIA_ROOT = BASE_DIR / 'media'

# Default comum: FileSystemStorage local. prod.py SOBRESCREVE STORAGES['default']
# para o backend S3/R2. staticfiles permanece local (servido pelo container) em
# todos os ambientes neste MVP.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Sentry (observabilidade) — TENANT-07 / TECH_SPEC §12.3 ---
# Init GUARDADO por SENTRY_DSN: em dev (DSN vazio) NAO inicializa, evitando
# qualquer envio acidental e mantendo a suite/check sem rede externa.
# `before_send` mascara email/telefone (PII) e send_default_pii=False barra o
# resto. A tag por tenant_id em cada evento e escopo da Sprint 7 — nao aqui.
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    from apps.core.sentry import before_send as _sentry_before_send

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        send_default_pii=False,
        before_send=_sentry_before_send,
    )
