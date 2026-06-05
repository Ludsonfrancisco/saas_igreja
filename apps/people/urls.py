"""URLs de Pessoas (namespace 'people'), tenant-scoped sob `pessoas/`.

Montadas UMA vez no ROOT_URLCONF. Todas as views aplicam TenantRequiredMixin →
respondem apenas em contexto de tenant (no schema public, 404).
"""

from django.urls import path

from apps.people.views import (
    PersonAnonymizeView,
    PersonCreateView,
    PersonDetailView,
    PersonExportView,
    PersonImportView,
    PersonListView,
    PersonUpdateView,
)

app_name = 'people'

urlpatterns = [
    path('pessoas/', PersonListView.as_view(), name='list'),
    path('pessoas/nova/', PersonCreateView.as_view(), name='create'),
    path('pessoas/importar/', PersonImportView.as_view(), name='import'),
    path('pessoas/<int:pk>/', PersonDetailView.as_view(), name='detail'),
    path('pessoas/<int:pk>/editar/', PersonUpdateView.as_view(), name='update'),
    path(
        'pessoas/<int:pk>/anonimizar/',
        PersonAnonymizeView.as_view(),
        name='anonymize',
    ),
    path('pessoas/<int:pk>/exportar/', PersonExportView.as_view(), name='export'),
]
