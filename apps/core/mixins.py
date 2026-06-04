"""Mixins de permissao e contexto de tenant (TENANT-05 / SEC-01 / P-ARQ-05).

Este modulo concentra os mixins de view exigidos pela arquitetura:

- `TenantRequiredMixin`: combina autenticacao com a garantia de que a view so e
  servida a partir de um schema de tenant real (TENANT-05 / AP-09).
- `RoleRequiredMixin` + subclasses (`PastorRequiredMixin`, `LeaderOrPastorMixin`,
  `TreasurerOrPastorMixin`): camada de view da autorizacao multi-role (RN-003a /
  P-ARQ-08). A verificacao e sempre via `has_any_role(*roles)` — uniao de
  papeis, nunca igualdade de campo unico.
- `ScopedToCommunityMixin` / `ScopedToMinistryMixin`: camada de queryset
  (P-ARQ-08). Pastor curto-circuita (ve tudo); outros papeis sao filtrados ao
  proprio escopo. Sao model-agnosticos (filtros por lookup string), prontos
  para as views de Community/Ministry da Sprint 3 — nao referenciam esses models.

Frente 5 (RN-015 / RISK-009 — Platform Admin & SupportAccess):

- `PlatformAdminRequiredMixin`: barreira das views da AREA DE PLATAFORMA, que
  vivem no schema `public` (espelho invertido do TenantRequiredMixin — exige
  estar NO public, e um PlatformAdmin ativo).
- `PlatformAdminWithSupportAccessMixin`: barreira (defense-in-depth) das views
  servidas DENTRO de um tenant a um Platform Admin: so libera com SupportAccess
  ativo, senao 403 + SecurityLog. O controle PRIMARIO de RISK-009 e o
  `PlatformAdminSupportMiddleware` (apps.core.middleware), que captura QUALQUER
  request de Platform Admin a um tenant — este mixin e a segunda linha.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404
from django.utils import timezone
from django_tenants.utils import get_public_schema_name


class TenantRequiredMixin(LoginRequiredMixin):
    """Exige usuario autenticado e contexto de tenant (TENANT-05 / SEC-01).

    `LoginRequiredMixin` garante a autenticacao. O `dispatch` adicional recusa
    qualquer acesso quando o request esta sendo servido a partir do schema
    `public` (ex.: acesso pela landing em `localhost`, sem subdominio de
    tenant). Nesse caso devolvemos HTTP 404 em vez de redirecionar para login
    ou revelar a existencia de rotas tenant-scoped no dominio publico, opcao
    mais conservadora em seguranca (P-ARQ-05 / SEC-01).
    """

    def dispatch(self, request, *args, **kwargs):
        if connection.schema_name == get_public_schema_name():
            raise Http404()
        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin:
    """Camada de view da autorizacao multi-role (RN-003a / P-ARQ-08).

    Subclasses definem `required_roles`; ter QUALQUER UM dos papeis listados
    libera o acesso (uniao de permissoes). A verificacao usa `has_any_role`,
    nunca igualdade de campo unico. Negacao levanta `PermissionDenied` (HTTP 403).

    Combine SEMPRE com `TenantRequiredMixin` (AP-01: decorator/role sem garantia
    de tenant e proibido). A ordem recomendada de MRO e
    `TenantRequiredMixin, <RoleMixin>, View` para que a barreira de tenant/login
    seja avaliada primeiro.
    """

    required_roles: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if not request.user.has_any_role(*self.required_roles):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class PastorRequiredMixin(RoleRequiredMixin):
    """Apenas Pastor pode acessar."""

    required_roles = ('pastor',)


class LeaderOrPastorMixin(RoleRequiredMixin):
    """Pastor ou Lider (qualquer um cobre). Escopo refinado em get_queryset."""

    required_roles = ('pastor', 'leader')


class TreasurerOrPastorMixin(RoleRequiredMixin):
    """Pastor ou Tesoureiro (pos-MVP)."""

    required_roles = ('pastor', 'treasurer')


class ScopedToCommunityMixin:
    """Camada de queryset: limita o escopo ao Lider da comunidade (P-ARQ-08).

    Pastor curto-circuita e ve tudo. Outros papeis veem apenas registros ligados
    a uma comunidade que LIDERAM. O vinculo e `Person.user_id` (TENANT-04: o staff
    Person guarda o id do User publico, NAO uma FK — por isso `__user_id`, e nao
    `__user__id`).

    Lookup configuravel via `community_scope_lookup`: numa queryset de `Community`
    e `leaders__user_id` (default; M2M OD-019); numa de `Person` (membros), a view
    sobrescreve para `community__leaders__user_id`.
    """

    community_scope_lookup = 'leaders__user_id'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.has_any_role('pastor'):
            return qs
        return qs.filter(**{self.community_scope_lookup: self.request.user.id})


class ScopedToMinistryMixin:
    """Camada de queryset: limita o escopo ao Coordenador do ministerio (P-ARQ-08).

    Espelha `ScopedToCommunityMixin`. Vinculo por `Person.user_id` (TENANT-04 →
    `__user_id`). Lookup configuravel via `ministry_scope_lookup`: numa queryset de
    `Ministry` e `coordinator__user_id` (default); numa de `Person`, a view usa
    `ministries__coordinator__user_id`.
    """

    ministry_scope_lookup = 'coordinator__user_id'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.has_any_role('pastor'):
            return qs
        return qs.filter(**{self.ministry_scope_lookup: self.request.user.id})


class PlatformAdminRequiredMixin:
    """Barreira das views da AREA DE PLATAFORMA (RN-015 / Frente 5).

    A area de plataforma (gestao de SupportAccess) vive no schema `public`, NAO
    dentro de um tenant — e o espelho invertido do `TenantRequiredMixin`:

    - exige usuario autenticado COM um `PlatformAdmin` ativo; senao
      `PermissionDenied` (HTTP 403);
    - exige estar NO schema `public`; servida de dentro de um tenant, devolve
      `Http404` (a area de plataforma nao e roteavel por subdominio de igreja, e
      nao revelamos sua existencia ali).
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        admin = getattr(request.user, 'platform_admin', None)
        if admin is None or not admin.is_active:
            raise PermissionDenied
        if connection.schema_name != get_public_schema_name():
            raise Http404()
        return super().dispatch(request, *args, **kwargs)


class PlatformAdminWithSupportAccessMixin:
    """Libera Platform Admin numa view de tenant so com SupportAccess ativo.

    RN-015 / RISK-009. Pega o `PlatformAdmin` do usuario; sem admin ou inativo,
    `PermissionDenied`. Com admin ativo, exige um `SupportAccess` vigente
    (`ended_at IS NULL AND expires_at > now`) para a igreja do request
    (`request.tenant`). Sem acesso: grava SecurityLog `platform_admin_access`
    com `denied=True` e levanta `PermissionDenied` (403).

    Defense-in-depth: o controle PRIMARIO de RISK-009 e o
    `PlatformAdminSupportMiddleware`, que bloqueia ANTES de qualquer view rodar.
    Na pratica o ramo de "deny" deste mixin quase nunca dispara — ele e a segunda
    linha caso o middleware seja removido/reordenado.

    Imports lazy no dispatch: evita o ciclo apps.core <-> apps.accounts no import.
    """

    def dispatch(self, request, *args, **kwargs):
        from apps.accounts.models import SupportAccess
        from apps.core.audit import log_security_event

        admin = getattr(request.user, 'platform_admin', None)
        if admin is None or not admin.is_active:
            raise PermissionDenied
        has_access = SupportAccess.objects.filter(
            admin=admin,
            church=request.tenant,
            ended_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists()
        if not has_access:
            log_security_event(
                event_type='platform_admin_access',
                user_id=request.user.id,
                payload={'denied': True, 'reason': 'no_active_support_access'},
            )
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
