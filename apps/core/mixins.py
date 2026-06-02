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

`PlatformAdminWithSupportAccessMixin` (RN-015 / Frente 5) NAO e implementado
aqui — depende do fluxo de SupportAccess, escopo de outra frente.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404
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
    """Camada de queryset: limita comunidades ao escopo do usuario (P-ARQ-08).

    Pastor curto-circuita e ve tudo. Outros papeis veem apenas comunidades onde
    sao lider. Filtro por lookup string puro (`leader__user__id`): este mixin e
    deliberadamente model-agnostico e NAO importa o model `Community` (que so
    nasce na Sprint 3). E estrutura para reuso nas views daquela sprint.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.has_any_role('pastor'):
            return qs
        return qs.filter(leader__user__id=self.request.user.id)


class ScopedToMinistryMixin:
    """Camada de queryset: limita ministerios ao escopo do usuario (P-ARQ-08).

    Pastor curto-circuita e ve tudo. Outros papeis veem apenas ministerios onde
    sao coordenador. Filtro por lookup string puro (`coordinator__user__id`);
    model-agnostico, NAO importa `Ministry` (Sprint 3).
    """

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.has_any_role('pastor'):
            return qs
        return qs.filter(coordinator__user__id=self.request.user.id)
