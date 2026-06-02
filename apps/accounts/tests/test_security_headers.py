"""Sprint 2 / Frente 2 — cabecalhos e cookies de seguranca em producao.

Valida que `core.settings.prod` define o bloco obrigatorio do PRD §15.3 / SEC-04.
Carregamos o modulo de prod isoladamente (sem trocar o settings do runner, que
roda em dev/DEBUG=False) e conferimos os valores exatos exigidos.

Carregar prod exige as mesmas env vars que base.py le via decouple (SECRET_KEY,
DATABASE_URL). O conftest/CI ja as fornece; aqui apenas importamos o modulo.
"""

import importlib

import pytest


@pytest.fixture(scope='module')
def prod_settings():
    """Modulo core.settings.prod carregado (valores estaticos do bloco SEC-04)."""
    return importlib.import_module('core.settings.prod')


def test_security_headers_present_in_prod(prod_settings):
    assert prod_settings.SECURE_SSL_REDIRECT is True
    assert prod_settings.SECURE_HSTS_SECONDS == 31536000
    assert prod_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod_settings.SECURE_HSTS_PRELOAD is True
    assert prod_settings.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod_settings.SECURE_BROWSER_XSS_FILTER is True
    assert prod_settings.SECURE_REFERRER_POLICY == 'strict-origin-when-cross-origin'
    assert prod_settings.X_FRAME_OPTIONS == 'DENY'


def test_session_cookies_secure_httponly_samesite(prod_settings):
    assert prod_settings.SESSION_COOKIE_SECURE is True
    assert prod_settings.SESSION_COOKIE_HTTPONLY is True
    assert prod_settings.SESSION_COOKIE_SAMESITE == 'Lax'
    assert prod_settings.CSRF_COOKIE_SECURE is True
    assert prod_settings.CSRF_COOKIE_HTTPONLY is True


def test_prod_debug_is_off(prod_settings):
    assert prod_settings.DEBUG is False
