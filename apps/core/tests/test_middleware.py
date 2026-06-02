"""Sprint 2 — AuditContextMiddleware: thread-local de ator do request.

O middleware carrega user_id+IP no thread-local durante o request e LIMPA no
finally (TECH_SPEC §2 / §5.9). Validamos os dois lados: durante o request os
helpers devolvem o usuario/IP corrente; depois (e fora de qualquer request) eles
voltam para None — invariante critico para nao vazar o ator de um request para o
proximo na mesma thread reusada.
"""

from types import SimpleNamespace

from apps.core.middleware import (
    AuditContextMiddleware,
    get_current_ip,
    get_current_user_id,
)


def _request(user=None, ip='203.0.113.7'):
    return SimpleNamespace(user=user, META={'REMOTE_ADDR': ip})


def _authed_user(user_id=42):
    return SimpleNamespace(id=user_id, is_authenticated=True)


def test_helpers_return_none_outside_request():
    # Sem request processado, o thread-local esta vazio (shell/Celery/anonimo).
    assert get_current_user_id() is None
    assert get_current_ip() is None


def test_middleware_sets_context_during_request():
    captured = {}

    def get_response(request):
        captured['user_id'] = get_current_user_id()
        captured['ip'] = get_current_ip()
        return 'response'

    middleware = AuditContextMiddleware(get_response)
    result = middleware(_request(user=_authed_user(7), ip='198.51.100.1'))

    assert result == 'response'
    assert captured['user_id'] == 7
    assert captured['ip'] == '198.51.100.1'

    # Limpo apos o request.
    assert get_current_user_id() is None
    assert get_current_ip() is None


def test_middleware_anonymous_user_has_none_user_id():
    captured = {}
    anon = SimpleNamespace(is_authenticated=False)

    def get_response(request):
        captured['user_id'] = get_current_user_id()
        return None

    AuditContextMiddleware(get_response)(_request(user=anon))

    assert captured['user_id'] is None


def test_middleware_clears_context_on_exception():
    def get_response(request):
        raise ValueError('boom')

    middleware = AuditContextMiddleware(get_response)

    try:
        middleware(_request(user=_authed_user(99)))
    except ValueError:
        pass

    # Mesmo com excecao na view, o finally limpa o thread-local.
    assert get_current_user_id() is None
    assert get_current_ip() is None
