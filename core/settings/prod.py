"""Settings de producao.

DEBUG desligado. Bloco de seguranca obrigatorio do TECH_SPEC §7.1 (SEC-04).
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
