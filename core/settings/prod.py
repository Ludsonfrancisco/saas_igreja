"""Settings de producao.

DEBUG desligado. Bloco de seguranca obrigatorio do TECH_SPEC §7.1 (SEC-04).

Storage de midia (Sprint 6 / OD-003a / OD-007 / RNF-018 / RISK-005): em prod o
`STORAGES['default']` aponta para Cloudflare R2 (S3-compatible) via
django-storages. dev/teste mantem o FileSystemStorage local definido em base.py.
A separacao existe porque (a) o R2 e privado e exige credenciais reais — ausentes
em dev/CI; (b) testes nao podem depender de rede/bucket externo. Credenciais via
env var (python-decouple), NUNCA hardcoded (SEC-06 / AP-12).
"""

from decouple import config

from .base import *  # noqa: F401,F403

DEBUG = False

# --- Email transacional via Brevo / anymail (OD-012) ---
# Backend Brevo do anymail. A BREVO_API_KEY vem de env var (python-decouple),
# nunca hardcoded (SEC-06 / AP-12). DEFAULT_FROM_EMAIL tem fallback em base.py.
# Chave real BREVO_API_KEY + DKIM/SPF no Cloudflare = Sprint 7 (OD-012).
EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'
ANYMAIL = {'BREVO_API_KEY': config('BREVO_API_KEY', default='')}
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='nao-responda@saasigreja.com')

# --- Bloco obrigatorio de seguranca (TECH_SPEC §7.1 / SEC-04) ---
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

# --- Storage de midia: Cloudflare R2 (S3-compatible) via django-storages ---
# OD-003a / OD-007 / RNF-018 / RISK-005 / RN-013. Bucket PRIVADO `saas-igreja-media`
# (OD-007: backups vao em bucket separado). Credenciais por env var, sem secret no
# repo (SEC-06 / AP-12) — placeholders vazios por padrao para nao quebrar coleta de
# settings; em prod o EasyPanel injeta os valores reais.
#
# Endpoint S3-compatible do R2: https://<account_id>.r2.cloudflarestorage.com
# (R2 ignora "regiao", mas a assinatura SigV4 exige uma; usamos 'auto').
R2_ACCESS_KEY_ID = config('R2_ACCESS_KEY_ID', default='')
R2_SECRET_ACCESS_KEY = config('R2_SECRET_ACCESS_KEY', default='')
R2_BUCKET_MEDIA = config('R2_BUCKET_MEDIA', default='saas-igreja-media')
R2_ENDPOINT_URL = config('R2_ENDPOINT_URL', default='')

STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'access_key': R2_ACCESS_KEY_ID,
            'secret_key': R2_SECRET_ACCESS_KEY,
            'bucket_name': R2_BUCKET_MEDIA,
            'endpoint_url': R2_ENDPOINT_URL,
            # R2 nao tem regioes; 'auto' satisfaz a assinatura SigV4.
            'region_name': 'auto',
            'signature_version': 's3v4',
            # path-style (bucket no path) e o esperado pelo endpoint R2.
            'addressing_style': 'path',
            # Bucket PRIVADO: sem ACL publica (RN-013 / RNF-018). None evita que o
            # django-storages envie cabecalho de ACL (R2 nem suporta ACLs).
            'default_acl': None,
            # Rede de seguranca: se `.url()` for chamado, sai ASSINADA (TTL curto),
            # nunca link publico permanente (RNF-018 / test_no_permanent_public_url).
            # Mas o download oficial NAO usa `.url()`: e streaming pela view
            # autenticada (OD-021, Bloco 3) — o controle de acesso fica na view.
            'querystring_auth': True,
            # Nao sobrescrever objeto existente silenciosamente; o path por tenant
            # ja inclui object_id, mas isto evita colisao de nome dentro do mesmo
            # objeto.
            'file_overwrite': False,
        },
    },
    # staticfiles permanece local (servido pelo container) — so a midia vai pro R2.
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
