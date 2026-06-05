"""URLs de arquivos (namespace 'files'), tenant-scoped sob `arquivos/`.

Bloco 3: apenas o download seguro por streaming (OD-021). A view aplica
`TenantRequiredMixin` (TENANT-05) + papel (ACCESS_MATRIX §3.8). Listagem e exclusao
autenticada entram no Bloco 4.
"""

from django.urls import path

from apps.files.views import FileDownloadView

app_name = 'files'

urlpatterns = [
    path(
        'arquivos/<int:pk>/download/',
        FileDownloadView.as_view(),
        name='download',
    ),
]
