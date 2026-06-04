"""URLs de Ministérios (namespace 'ministries'), tenant-scoped sob `ministerios/`."""

from django.urls import path

from apps.ministries.views import (
    MinistryCreateView,
    MinistryDeleteView,
    MinistryDetailView,
    MinistryListView,
    MinistryUpdateView,
)

app_name = 'ministries'

urlpatterns = [
    path('ministerios/', MinistryListView.as_view(), name='list'),
    path('ministerios/novo/', MinistryCreateView.as_view(), name='create'),
    path('ministerios/<int:pk>/', MinistryDetailView.as_view(), name='detail'),
    path('ministerios/<int:pk>/editar/', MinistryUpdateView.as_view(), name='update'),
    path(
        'ministerios/<int:pk>/excluir/',
        MinistryDeleteView.as_view(),
        name='delete',
    ),
]
