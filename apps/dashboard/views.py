"""Views do dashboard, escopadas por papel (Sprint 6 / Bloco 5).

RF-070..072 / ACCESS_MATRIX §3.9. Tres dashboards, um por nivel de escopo:

- `DashboardPastorView`  — completo (Pastor). Sem recorte.
- `DashboardLeaderView`  — simplificado da comunidade (Pastor + Lider). Escopo =
  comunidades que o usuario LIDERA.
- `DashboardCoordinatorView` — simplificado do ministerio (Pastor + Coordenador).
  Escopo = ministerios que o usuario COORDENA.

Defesa em profundidade (P-ARQ-08):
- camada de view: `TenantRequiredMixin` (TENANT-05/AP-09) + papel
  (`PastorRequiredMixin`/`LeaderOrPastorMixin`).
- camada de service/queryset: o recorte fino vive em `church_metrics`, que agrega
  no banco do TENANT ATUAL (TENANT-04) — sem vazamento cross-tenant (RISK-001).

Pastor nos dashboards simplificados (§3.9 "Pastor ✅ em tudo"): curto-circuita para
a VISAO COMPLETA. Sem o curto-circuito, um Pastor (que normalmente nao lidera
comunidade/ministerio) veria zeros — o que contraria a matriz. Lider/Coordenador NAO
curto-circuita: ve so o proprio escopo, e zeros se nao lidera nada (conservador).

Nao existe papel `coordinator` em `User.Role`: "Coordenador" e o papel `leader`
aplicado a um Ministerio (mesma convencao de `files`/`schedules`). Por isso o
`DashboardCoordinatorView` usa `LeaderOrPastorMixin` e recorta por
`Ministry.coordinators__user_id`.
"""

from django.views.generic import TemplateView

from apps.communities.models import Community
from apps.core.mixins import (
    LeaderOrPastorMixin,
    PastorRequiredMixin,
    TenantRequiredMixin,
)
from apps.dashboard.services import church_metrics
from apps.ministries.models import Ministry


class DashboardPastorView(TenantRequiredMixin, PastorRequiredMixin, TemplateView):
    """Dashboard completo da igreja — APENAS Pastor (§3.9 "completo")."""

    template_name = 'dashboard/dashboard_pastor.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['metrics'] = church_metrics()
        return context


class DashboardLeaderView(TenantRequiredMixin, LeaderOrPastorMixin, TemplateView):
    """Dashboard simplificado da comunidade — Pastor + Lider (§3.9, sua comunidade).

    Escopo = comunidades que o usuario lidera (`Community.leaders__user_id`, mesma
    fonte de verdade dos `ScopedTo*` do core e do `ScopedFileQuerysetMixin`). Pastor
    curto-circuita para a visao completa.
    """

    template_name = 'dashboard/dashboard_leader.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.has_any_role('pastor', 'secretary'):
            context['metrics'] = church_metrics()
        else:
            community_ids = list(
                Community.objects.filter(
                    leaders__user_id=self.request.user.id
                ).values_list('id', flat=True)
            )
            context['metrics'] = church_metrics(community_ids=community_ids)
        return context


class DashboardCoordinatorView(TenantRequiredMixin, LeaderOrPastorMixin, TemplateView):
    """Dashboard simplificado do ministerio — Pastor + Coordenador (§3.9, seu).

    Escopo = ministerios que o usuario coordena (`Ministry.coordinators__user_id`,
    mesma fonte de verdade dos `ScopedTo*` do core). "Coordenador" e o papel `leader`
    aplicado a um Ministerio (nao ha papel `coordinator`). Pastor curto-circuita.
    """

    template_name = 'dashboard/dashboard_coordinator.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.has_any_role('pastor', 'secretary'):
            context['metrics'] = church_metrics()
        else:
            ministry_ids = list(
                Ministry.objects.filter(
                    coordinators__user_id=self.request.user.id
                ).values_list('id', flat=True)
            )
            context['metrics'] = church_metrics(ministry_ids=ministry_ids)
        return context
