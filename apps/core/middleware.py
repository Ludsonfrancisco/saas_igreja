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

`PlatformAdminSupportMiddleware` (Frente 5, RN-015 / RISK-009): controle
PRIMARIO de acesso de Platform Admin a tenants. Captura QUALQUER request a um
tenant feita por um Platform Admin (nao so views com mixin) e exige SupportAccess
ativo, auditando cada acesso/negacao em SecurityLog. Ver a classe abaixo.

MFARequiredForRoleMiddleware (Sprint 7, RISK-013): o enforcement obrigatorio de
MFA para `pastor`/`PlatformAdmin` vivera AQUI neste modulo. NAO implementar
agora — fora do escopo da Sprint 2 (apenas MFA opt-in).
"""

import threading

from django.db import connection
from django.http import HttpResponseForbidden
from django.utils import timezone
from django_tenants.utils import get_public_schema_name

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


class PlatformAdminSupportMiddleware:
    """Enforcement global de SupportAccess para Platform Admin (RN-015 / RISK-009).

    Controle PRIMARIO de RISK-009: toda request a um TENANT feita por um Platform
    Admin passa por aqui — nao apenas as views que aplicam o mixin. Garante que um
    Platform Admin so toque um schema de igreja quando ha `SupportAccess` ativo, e
    audita CADA acesso (concedido ou negado) no SecurityLog do proprio tenant.

    Caminho rapido (custo do middleware no fluxo normal):
    - request no schema `public` -> nada a fazer (a area de plataforma e tratada
      pelo `PlatformAdminRequiredMixin`); segue.
    - usuario nao autenticado -> segue (login e tratado adiante).
    - dentro de um tenant + autenticado: 1 query indexada `PlatformAdmin` por
      user_id. Usuario comum da igreja (a esmagadora maioria) -> None -> segue.
      So dispara a logica de SupportAccess para Platform Admins de fato.

    Quando o user E Platform Admin ativo dentro de um tenant:
    - SEM SupportAccess vigente -> SecurityLog(denied=True) e HTTP 403 (NAO chama
      get_response: bloqueia a request por completo).
    - COM SupportAccess vigente -> SecurityLog(denied=False, support_access_id) e
      segue para a view.

    O log roda em contexto de tenant (search_path ja aponta para o schema da
    igreja), logo grava no SecurityLog do tenant correto — sem `schema_context`.

    Ordem no MIDDLEWARE: DEPOIS de `AuditContextMiddleware`. Precisa de
    `request.user` (AuthenticationMiddleware), de `request.tenant` e do schema ja
    resolvido (TenantMiddleware, no topo). Como bloqueia ANTES de a view rodar, o
    ramo de "deny" do `PlatformAdminWithSupportAccessMixin` e defense-in-depth e
    praticamente nunca dispara; no caminho de "allow" so o middleware loga, sem
    duplicar o evento por request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if connection.schema_name == get_public_schema_name():
            return self.get_response(request)

        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return self.get_response(request)

        # Import tardio: PlatformAdmin vive em apps.accounts; evita ciclo no
        # carregamento de apps.core.
        from apps.accounts.models import PlatformAdmin, SupportAccess
        from apps.core.audit import log_security_event

        admin = PlatformAdmin.objects.filter(user_id=user.id, is_active=True).first()
        if admin is None:
            # Usuario comum da igreja: caminho normal, sem enforcement.
            return self.get_response(request)

        support_access = SupportAccess.objects.filter(
            admin=admin,
            church=request.tenant,
            ended_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).first()

        if support_access is None:
            log_security_event(
                event_type='platform_admin_access',
                user_id=user.id,
                payload={
                    'denied': True,
                    'reason': 'no_active_support_access',
                    'path': request.path,
                },
            )
            return HttpResponseForbidden('Acesso negado: sem SupportAccess ativo.')

        log_security_event(
            event_type='platform_admin_access',
            user_id=user.id,
            payload={
                'denied': False,
                'support_access_id': support_access.id,
                'path': request.path,
            },
        )
        return self.get_response(request)
