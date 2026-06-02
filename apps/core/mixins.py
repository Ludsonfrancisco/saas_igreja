"""Mixins de permissao e contexto de tenant (TENANT-05 / SEC-01 / P-ARQ-05).

Este modulo concentra os mixins de view exigidos pela arquitetura. Por ora
apenas `TenantRequiredMixin` existe: ele combina autenticacao com a garantia
de que a view so e servida a partir de um schema de tenant real.

Os mixins de papel/escopo (`PastorRequiredMixin`, `RoleRequiredMixin`,
`LeaderOrPastorMixin`, `TreasurerOrPastorMixin`, `ScopedToCommunityMixin`,
`ScopedToMinistryMixin`, `PlatformAdminWithSupportAccessMixin`) sao escopo da
Sprint 2 e NAO sao implementados aqui.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
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
