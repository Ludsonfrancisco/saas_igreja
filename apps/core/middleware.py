"""Middlewares de suporte a auditoria e (futuro) enforcement de MFA.

`AuditContextMiddleware` captura, por request, o usuario autenticado e o IP do
cliente em um thread-local. Isso permite que os signals de auditoria
(`apps.core.signals`) descubram QUEM executou uma operacao mesmo quando o save
acontece bem longe da view (service layer, post_save em cascata, etc.), sem ter
de propagar `request` por toda a stack.

Por que thread-local e nao tudo via `connection`? O `tenant_id` ja vem de
`connection.schema_name` (django-tenants seta o search_path por request), entao
NAO precisa de thread-local. Apenas `user_id` e `ip_address` precisam ser
carregados — eles vivem no `request`, nao na connection (TECH_SPEC §2 / §5.9).

Fora de um request (shell, Celery, testes que nao passam pela stack HTTP) o
thread-local fica vazio e os helpers retornam None: o auditing degrada para
"sistema/anonimo" em vez de quebrar.

MFARequiredForRoleMiddleware (Sprint 7, RISK-013): o enforcement obrigatorio de
MFA para `pastor`/`PlatformAdmin` vivera AQUI neste modulo. NAO implementar
agora — fora do escopo da Sprint 2 (apenas MFA opt-in).
"""

import threading

_audit_context = threading.local()


def _get_client_ip(request):
    """Extrai o IP do cliente do request.

    Le `REMOTE_ADDR` diretamente. NAO confiamos em `X-Forwarded-For` aqui: sem
    uma lista de proxies confiaveis configurada, o header e spoofavel pelo
    cliente (opcao mais conservadora em seguranca). Quando o deploy estiver
    atras de um proxy confiavel (Sprint 7), a resolucao de XFF sera feita de
    forma controlada — nao por leitura ingenua do header.
    """
    return request.META.get('REMOTE_ADDR')


class AuditContextMiddleware:
    """Carrega user_id + IP do request atual em um thread-local.

    Os signals de auditoria leem esse contexto via `get_current_user_id()` /
    `get_current_ip()`. O thread-local e sempre limpo no `finally`, inclusive
    quando a view levanta excecao, para nunca vazar o contexto de um request
    para o proximo (threads sao reusadas pelo servidor WSGI).

    Ordem no MIDDLEWARE: depois de `AuthenticationMiddleware` (precisa de
    `request.user`) e de `TenantMiddleware` (mantido no topo).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        _audit_context.user_id = (
            user.id if user is not None and user.is_authenticated else None
        )
        _audit_context.ip_address = _get_client_ip(request)
        try:
            return self.get_response(request)
        finally:
            # Limpa SEMPRE: request normal, redirect ou excecao. Evita vazar o
            # ator de um request para o proximo na mesma thread reusada.
            _audit_context.user_id = None
            _audit_context.ip_address = None


def get_current_user_id():
    """Retorna o id do usuario do request atual, ou None fora de um request.

    None significa "sem ator HTTP" (shell, Celery, request anonimo). O caller de
    auditoria pode passar um user_id explicito para sobrepor.
    """
    return getattr(_audit_context, 'user_id', None)


def get_current_ip():
    """Retorna o IP do request atual, ou None fora de um request."""
    return getattr(_audit_context, 'ip_address', None)
