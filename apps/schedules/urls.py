"""URLs de Escalas (namespace 'schedules'), tenant-scoped sob `escalas/`.

As views de CRUD aplicam `TenantRequiredMixin` (TENANT-05). Exceção: a rota
PÚBLICA do magic-link do voluntário (`voluntario/escala/<token>/`, OD-022) é
read-only SEM login — tenant-scoped pelo subdomínio + token assinado com bind de
tenant (apps/schedules/tokens.py).
"""

from django.urls import path

from apps.schedules.views import (
    MinistryEventOptOutView,
    ScheduleCreateView,
    ScheduleDeleteView,
    ScheduleDetailView,
    ScheduleEventListView,
    ScheduleEventModalView,
    ScheduleExceptionCreateView,
    ScheduleListView,
    ScheduleUpdateView,
    VolunteerScheduleView,
)

app_name = 'schedules'

urlpatterns = [
    # Escalas v2 (coordenador-cêntrica): entrada por evento + modal de escalação.
    path('escalas/eventos/', ScheduleEventListView.as_view(), name='events'),
    path(
        'escalas/eventos/<int:pk>/escalar/',
        ScheduleEventModalView.as_view(),
        name='event_modal',
    ),
    path(
        'escalas/eventos/<int:pk>/ministerio/<int:ministry_pk>/atuacao/',
        MinistryEventOptOutView.as_view(),
        name='event_optout',
    ),
    # CRUD clássico (Sprint 5) — lista detalhada de registros.
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
    # PÚBLICA (sem login) — magic-link read-only do voluntário (OD-022).
    path(
        'voluntario/escala/<str:token>/',
        VolunteerScheduleView.as_view(),
        name='volunteer',
    ),
]
