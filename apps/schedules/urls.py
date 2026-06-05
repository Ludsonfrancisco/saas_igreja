"""URLs de Escalas (namespace 'schedules'), tenant-scoped sob `escalas/`.

Todas as views aplicam `TenantRequiredMixin` (TENANT-05). A aprovação de exceção
de conflito entra na Frente 2.
"""

from django.urls import path

from apps.schedules.views import (
    ScheduleCreateView,
    ScheduleDeleteView,
    ScheduleDetailView,
    ScheduleExceptionCreateView,
    ScheduleListView,
    ScheduleUpdateView,
)

app_name = 'schedules'

urlpatterns = [
    path('escalas/', ScheduleListView.as_view(), name='list'),
    path('escalas/nova/', ScheduleCreateView.as_view(), name='create'),
    path(
        'escalas/excecao/nova/',
        ScheduleExceptionCreateView.as_view(),
        name='exception',
    ),
    path('escalas/<int:pk>/', ScheduleDetailView.as_view(), name='detail'),
    path('escalas/<int:pk>/editar/', ScheduleUpdateView.as_view(), name='update'),
    path('escalas/<int:pk>/excluir/', ScheduleDeleteView.as_view(), name='delete'),
]
