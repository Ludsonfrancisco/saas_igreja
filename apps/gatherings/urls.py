"""URLs de Encontros (namespace 'gatherings'), tenant-scoped sob `encontros/`.

Todas as views aplicam `TenantRequiredMixin` (TENANT-05).
"""

from django.urls import path

from apps.gatherings.views import (
    AttendanceMarkView,
    GatheringCreateView,
    GatheringDeleteView,
    GatheringDetailView,
    GatheringListView,
    GatheringUpdateView,
)

app_name = 'gatherings'

urlpatterns = [
    path('encontros/', GatheringListView.as_view(), name='list'),
    path('encontros/novo/', GatheringCreateView.as_view(), name='create'),
    path('encontros/<int:pk>/', GatheringDetailView.as_view(), name='detail'),
    path('encontros/<int:pk>/editar/', GatheringUpdateView.as_view(), name='update'),
    path('encontros/<int:pk>/excluir/', GatheringDeleteView.as_view(), name='delete'),
    path(
        'encontros/<int:pk>/presenca/',
        AttendanceMarkView.as_view(),
        name='attendance',
    ),
]
