"""URLs de arquivos (namespace 'files'), tenant-scoped sob `arquivos/`.

Bloco 3: download seguro por streaming (OD-021).
Bloco 4: listagem com escopo por papel/contexto + exclusao (apenas Pastor). Toda
view aplica `TenantRequiredMixin` (TENANT-05) + camada de papel (ACCESS_MATRIX §3.8).
"""

from django.urls import path

from apps.files.views import (
    FileAssetListView,
    FileDeleteView,
    FileDownloadView,
    FileUploadView,
)

app_name = 'files'

urlpatterns = [
    path('arquivos/', FileAssetListView.as_view(), name='list'),
    path('arquivos/enviar/', FileUploadView.as_view(), name='upload'),
    path(
        'arquivos/<int:pk>/download/',
        FileDownloadView.as_view(),
        name='download',
    ),
    path(
        'arquivos/<int:pk>/excluir/',
        FileDeleteView.as_view(),
        name='delete',
    ),
]
