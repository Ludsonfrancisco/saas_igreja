"""URLs de Comunidades (namespace 'communities'), tenant-scoped sob `comunidades/`.

Todas as views aplicam `TenantRequiredMixin` + `CommunitiesEnabledMixin` (404 se a
igreja não usa comunidades).
"""

from django.urls import path

from apps.communities.views import (
    CommunityCreateView,
    CommunityDeleteView,
    CommunityDetailView,
    CommunityListView,
    CommunityUpdateView,
)

app_name = 'communities'

urlpatterns = [
    path('comunidades/', CommunityListView.as_view(), name='list'),
    path('comunidades/nova/', CommunityCreateView.as_view(), name='create'),
    path('comunidades/<int:pk>/', CommunityDetailView.as_view(), name='detail'),
    path('comunidades/<int:pk>/editar/', CommunityUpdateView.as_view(), name='update'),
    path(
        'comunidades/<int:pk>/excluir/',
        CommunityDeleteView.as_view(),
        name='delete',
    ),
]
