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

import re
from datetime import date

from django.http import Http404
from django.utils import timezone
from django.views.generic import TemplateView

from apps.communities.models import Community
from apps.core.mixins import (
    LeaderOrPastorMixin,
    PastorRequiredMixin,
    TenantRequiredMixin,
)
from apps.dashboard.services import (
    MONTH_NAMES_PT,
    WEEKDAY_LABELS_PT,
    build_calendar_weeks,
    church_metrics,
    event_days,
    gatherings_on_day,
    home_growth_series,
    ministry_health,
    ministry_volunteer_gaps,
    upcoming_gatherings,
)
from apps.ministries.models import Ministry


def _scoped_ministry_ids(user):
    """ids dos ministérios no escopo do `user` p/ a Saúde do Ministério (§3.9).

    Pastor/Secretário => `None` (todos). Demais => os que coordenam
    (`Ministry.coordinators__user_id`); quem não coordena nada => `[]` (vazio =
    zero, conservador, nunca a visão completa).
    """
    if user.has_any_role('pastor', 'secretary'):
        return None
    return list(
        Ministry.objects.filter(coordinators__user_id=user.id).values_list(
            'id', flat=True
        )
    )


def _scoped_ministry_gaps(user):
    """GAP de voluntários no escopo do `user` (lista) — retrocompat p/ templates."""
    return ministry_volunteer_gaps(ministry_ids=_scoped_ministry_ids(user))


def _sparkline(values, *, width=100, height=30, pad=3):
    """Converte uma série numérica em pontos SVG (polyline) + último ponto.

    Escala linear min→max no eixo Y (invertido p/ SVG). Série constante vira uma
    linha no meio. Retorna `{'points': 'x,y ...', 'last_x', 'last_y'}` (1 casa).
    """
    n = len(values)
    if n == 0:
        return {'points': '', 'last_x': 0, 'last_y': height / 2}
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    inner = height - 2 * pad
    step = width / (n - 1) if n > 1 else 0
    pts = []
    for i, v in enumerate(values):
        x = round(i * step, 1)
        y = round(pad + inner - (v - lo) / span * inner, 1)
        pts.append((x, y))
    return {
        'points': ' '.join(f'{x},{y}' for x, y in pts),
        'last_x': pts[-1][0],
        'last_y': pts[-1][1],
    }


def _calendar_year_month(request):
    """(year, month) do calendário, vindos de `?year=&month=` ou o mês atual (RF-102).

    Tolera ausência/lixo nos parâmetros (cai no mês atual) e valida `1 <= month <= 12`.
    A troca de mês na home chega por estes parâmetros via HTMX (`HomeCalendarView`).
    """
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        return today.year, today.month
    if not 1 <= month <= 12:
        return today.year, today.month
    return year, month


def _safe_dom_id(value, default):
    """Sanitiza um id/seletor vindo de querystring (`?cal_id=&day_target=`) antes de
    ecoá-lo em atributos `id`/`hx-target`. Só `[A-Za-z0-9_-]` (1–40); senão, default."""
    if value and re.fullmatch(r'[A-Za-z0-9_-]{1,40}', value):
        return value
    return default


def calendar_context(request):
    """Contexto do calendário do mês pedido (RF-102). Público porque é reaproveitado
    fora do dashboard: o calendário saiu da home (OD-030) e foi wirado na página de
    Encontros (`GatheringListView`), que monta o mesmo card a partir daqui. Também
    alimenta o fragmento de troca de mês (`HomeCalendarView`).

    Inclui a matriz de semanas (dias com evento marcados), os rótulos pt-BR, o mês
    anterior/seguinte (para os botões de navegação) e `today`.
    """
    today = timezone.localdate()
    year, month = _calendar_year_month(request)
    days = event_days(year=year, month=month)
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return {
        'calendar_year': year,
        'calendar_month': month,
        'calendar_label': f'{MONTH_NAMES_PT[month]} {year}',
        'calendar_weekdays': WEEKDAY_LABELS_PT,
        'calendar_weeks': build_calendar_weeks(
            year=year, month=month, event_days=days, today=today
        ),
        'calendar_prev': {'year': prev_year, 'month': prev_month},
        'calendar_next': {'year': next_year, 'month': next_month},
        'event_days': days,
        'today_iso': today.isoformat(),
        # IDs do card/alvo do dia — parametrizáveis p/ o calendário coexistir em mais
        # de um lugar (drawer da agenda vs. home) sem colidir. Sanitizados porque vêm
        # do `?cal_id=&day_target=` (vão para atributos id/hx-target).
        'cal_id': _safe_dom_id(request.GET.get('cal_id'), 'home-calendar'),
        'day_target': _safe_dom_id(request.GET.get('day_target'), 'day-panel'),
    }


class HomeView(TenantRequiredMixin, TemplateView):
    """Home nova "Painel Oikonos" (Sprint 6.6 / design igreja-athos-dashboard).

    Aberta a qualquer usuário logado do tenant (RF-102/103 "Todos") — o gate é só
    `TenantRequiredMixin` (TENANT-05/AP-09). Composição (decisões do dono 2026-06-09):

    - KPIs (Pessoas/Comunidades/Ministérios/Presenças): `church_metrics()` do tenant
      (visão da igreja — contagens agregadas, P-ARQ-09).
    - Saúde do Ministério = GAP de voluntários (RF-104 / OD-029): card escuro, dado
      REAL, escopado por papel (Pastor vê todos; Coordenador só os que coordena).
    - Próximas programações (RF-103): encontros futuros do tenant.
    - Escalas (próximas): contagem de `Schedule` de encontros futuros.
    - Seções sem backend (Financeiro, Tendências, Frequência, Radar, Atividades):
      placeholder "Em breve" no template (sem números fictícios).

    O calendário (RF-102) saiu da home (OD-030) e foi wirado na página de Encontros
    (`GatheringListView`); os fragmentos `HomeCalendarView`/`HomeDayView` (troca de
    mês e encontros do dia) seguem servindo de lá via HTMX.
    """

    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        from apps.schedules.models import Schedule

        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context['metrics'] = church_metrics()
        # Saúde do Ministério = GAP em % + por ministério (escopado por papel).
        context['health'] = ministry_health(
            ministry_ids=_scoped_ministry_ids(self.request.user)
        )
        context['upcoming_gatherings'] = upcoming_gatherings()
        # KPI "Escalas" = escalas de encontros futuros (contagem no banco).
        context['upcoming_schedules_count'] = Schedule.objects.filter(
            gathering__date__gte=today
        ).count()
        # Sparklines reais (crescimento mensal) p/ os cards de KPI.
        series = home_growth_series()
        context['spark_people'] = _sparkline(series['people'])
        context['spark_communities'] = _sparkline(series['communities'])
        context['spark_schedules'] = _sparkline(series['schedules'])
        return context


class HomeCalendarView(TenantRequiredMixin, TemplateView):
    """Fragmento do calendário (RF-102) — troca de mês via HTMX (`hx-get`).

    Devolve só o card do calendário (`_calendar.html`) para o swap. Mesmo gate de
    tenant da home; sem dados sensíveis (só dias com encontro do mês pedido).
    """

    template_name = 'dashboard/_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(calendar_context(self.request))
        return context


class HomeDayView(TenantRequiredMixin, TemplateView):
    """Fragmento "encontros do dia" (RF-102) — clique numa célula do calendário.

    Recebe a data ISO na URL; devolve a lista de encontros daquele dia (`_day.html`).
    Data inválida => 404 (não vaza). Visão do tenant inteiro (§3.6).
    """

    template_name = 'dashboard/_day.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            day = date.fromisoformat(self.kwargs['day'])
        except (TypeError, ValueError):
            raise Http404('Data inválida.') from None
        context['day'] = day
        context['day_gatherings'] = gatherings_on_day(day)
        return context


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
