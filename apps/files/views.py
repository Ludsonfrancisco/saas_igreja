"""Views de arquivos — download seguro por streaming (Sprint 6 / Bloco 3).

Apenas a VIEW DE DOWNLOAD entra no Bloco 3. Listagem (com filtros por contexto) e
exclusao autenticada sao Bloco 4 — fora de escopo aqui.

Mecanismo de download (OD-021): STREAMING pela propria view autenticada, NUNCA
redirect para URL assinada do R2 nem exposicao de `file_asset.file.url`. O controle
de acesso fica 100% na view, a cada request — zero URL publica permanente (RNF-018 /
RISK-005 / `test_no_permanent_public_url`). A mesma rota funciona em dev (FS) e prod
(R2) sem mock de S3.

Defesa em profundidade (P-ARQ-08):
- camada de view: `TenantRequiredMixin` (TENANT-05/AP-09) + papel
  (`FileDownloadRoleMixin`, ACCESS_MATRIX §3.8 linha "Download de arquivo");
- camada de queryset: o `FileAsset` e resolvido SOMENTE no schema do tenant atual
  (FileAsset e model de TENANT). Outro tenant ou inexistente => Http404 (NUNCA 403
  — nao revelamos a existencia do arquivo, RISK-001).

Auditoria: o download dispara o sinal custom `files.signals.file_downloaded`, que
grava AuditLog 'read' + SecurityLog 'sensitive_file_download' (Bloco 3). A view nao
chama os helpers de audit diretamente — mantem a auditoria centralizada em signals
(P-ARQ-06), igual ao resto do projeto.
"""

from django.views import View
from django.views.generic.detail import SingleObjectMixin

from apps.core.mixins import RoleRequiredMixin, TenantRequiredMixin
from apps.files.models import FileAsset
from apps.files.responses import stream_file_asset
from apps.files.signals import file_downloaded


class FileDownloadRoleMixin(RoleRequiredMixin):
    """Camada de PAPEL do download (ACCESS_MATRIX §3.8 "Download de arquivo").

    Pastor (✅), Secretario, Lider/Coordenador e Tesoureiro (🟡 — com escopo)
    podem baixar. Platform Admin e explicitamente ❌ (nao tem papel de igreja em
    `User.roles`). Membro nao tem login no MVP (OD-004), entao nao alcanca a rota.

    O ESCOPO fino "(autorizado)" da matriz (visibilidade por `related_model`/
    contexto) e refinado no Bloco 4 (listagem + filtro). No Bloco 3 a barreira de
    papel ja exclui Platform Admin e qualquer nao-autenticado; o isolamento por
    tenant (404 cross-tenant) e garantido pelo queryset abaixo.
    """

    required_roles = ('pastor', 'secretary', 'leader', 'treasurer')


class FileDownloadView(
    TenantRequiredMixin, FileDownloadRoleMixin, SingleObjectMixin, View
):
    """Faz streaming dos bytes de um `FileAsset` do tenant atual (OD-021).

    Cross-tenant ou inexistente => 404 (SingleObjectMixin.get_object levanta
    Http404). O `FileAsset` vive no schema do tenant, entao o queryset ja esta
    naturalmente escopado — nao ha como alcancar o arquivo de outra igreja.
    """

    model = FileAsset
    context_object_name = 'file_asset'

    def get(self, request, *args, **kwargs):
        file_asset = self.get_object()
        response = stream_file_asset(file_asset)
        # Auditoria centralizada em signals (P-ARQ-06): AuditLog 'read' +
        # SecurityLog 'sensitive_file_download'. user_id = ator do request
        # (TENANT-04: id do User publico).
        file_downloaded.send(
            sender=self.__class__,
            file_asset=file_asset,
            user_id=request.user.id,
        )
        return response
