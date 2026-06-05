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
)

app_name = 'dashboard'

urlpatterns = [
    path('painel/', DashboardPastorView.as_view(), name='pastor'),
    path('painel/comunidade/', DashboardLeaderView.as_view(), name='leader'),
    path('painel/ministerio/', DashboardCoordinatorView.as_view(), name='coordinator'),
]
