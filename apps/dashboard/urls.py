"""URLs do dashboard (namespace 'dashboard'), tenant-scoped sob `painel/`.

Sprint 6 / Bloco 5 (ACCESS_MATRIX §3.9). Toda view aplica `TenantRequiredMixin`
(TENANT-05) + camada de papel. Tres rotas, uma por nivel de escopo:

- `painel/`             -> completo (Pastor);
- `painel/comunidade/`  -> simplificado da comunidade (Pastor + Lider);
- `painel/ministerio/`  -> simplificado do ministerio (Pastor + Coordenador).
"""

from django.urls import path

from apps.dashboard.views import (
    DashboardCoordinatorView,
    DashboardLeaderView,
    DashboardPastorView,
    HomeCalendarView,
    HomeDayView,
)

app_name = 'dashboard'

urlpatterns = [
    # Home nova (Sprint 6.6): a PÁGINA vive em `/` (raiz, `core/urls.py` -> HomeView).
    # Aqui ficam só os FRAGMENTOS HTMX do calendário da home:
    #  - troca de mês (`?year=&month=`), e
    #  - encontros de um dia (clique numa célula).
    path('inicio/calendario/', HomeCalendarView.as_view(), name='home_calendar'),
    path('inicio/dia/<str:day>/', HomeDayView.as_view(), name='home_day'),
    path('painel/', DashboardPastorView.as_view(), name='pastor'),
    path('painel/comunidade/', DashboardLeaderView.as_view(), name='leader'),
    path('painel/ministerio/', DashboardCoordinatorView.as_view(), name='coordinator'),
]
