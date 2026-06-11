"""Views de arquivos — download, listagem e exclusao (Sprint 6 / Blocos 3 e 4).

Bloco 3 entregou o download seguro por streaming. O Bloco 4 acrescenta:
- `FileAssetListView` (RF-066): listagem com escopo por papel/contexto + filtros;
- `FileDeleteView` (RF-068): exclusao APENAS-Pastor (ACCESS_MATRIX §3.8);
- `ScopedFileQuerysetMixin`: o escopo por contexto, extraido para ser reusado pela
  listagem E pelo download (fecha a pendencia "(autorizado)" do Bloco 3 — DRY).

Mecanismo de download (OD-021): STREAMING pela propria view autenticada, NUNCA
redirect para URL assinada do R2 nem exposicao de `file_asset.file.url`. O controle
de acesso fica 100% na view, a cada request (RNF-018 / RISK-005).

Defesa em profundidade (P-ARQ-08):
- camada de view: `TenantRequiredMixin` (TENANT-05/AP-09) + papel
  (`RoleRequiredMixin`/subclasses, ACCESS_MATRIX §3.8);
- camada de queryset: `FileAsset` resolvido SOMENTE no schema do tenant atual
  (TENANT-04) + escopo fino por contexto (`ScopedFileQuerysetMixin`). Outro tenant
  ou fora do escopo => Http404 (NUNCA 403 — nao revelamos a existencia do arquivo,
  RISK-001).

Auditoria:
- download dispara o sinal custom `files.signals.file_downloaded` (AuditLog 'read'
  + SecurityLog 'sensitive_file_download');
- delete gera AuditLog 'delete' automatico (FileAsset herda AuditLogMixin). Nao ha
  event_type de SecurityLog dedicado a exclusao em `SecurityLog.EVENT_CHOICES`; por
  decisao da task NAO criamos migration — o AuditLog 'delete' cobre a trilha.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, FormView, ListView
from django.views.generic.detail import SingleObjectMixin

from apps.communities.models import Community
from apps.core.mixins import (
    PastorOrSecretaryMixin,
    PastorRequiredMixin,
    RoleRequiredMixin,
    TenantRequiredMixin,
)
from apps.files import services
from apps.files.forms import FileUploadForm
from apps.files.models import FileAsset
from apps.files.responses import stream_file_asset
from apps.files.signals import file_downloaded
from apps.ministries.models import Ministry

# Valores de `FileAsset.related_model` usados como contexto de escopo. Strings,
# nao FKs (TECH_SPEC §5.8) — alinhados aos contextos de upload da ACCESS_MATRIX
# §3.8 (comunidade / ministerio / financeiro).
CONTEXT_COMMUNITY = 'community'
CONTEXT_MINISTRY = 'ministry'
CONTEXT_FINANCE = 'finance'


class FileAccessRoleMixin(RoleRequiredMixin):
    """Camada de PAPEL para listar/baixar arquivos (ACCESS_MATRIX §3.8).

    Pastor (✅) e Secretario veem/baixam tudo; Lider/Coordenador e Tesoureiro
    entram com escopo fino ("(visiveis)/(autorizado)"), refinado no
    `ScopedFileQuerysetMixin`. Platform Admin e ❌ (nao tem papel de igreja em
    `User.roles`); Membro nao tem login no MVP (OD-004).

    Nao existe papel `coordinator` em `User.Role`: "Coordenador" e o papel `leader`
    aplicado a um Ministerio (mesma convencao de `schedules.PastorOrCoordinatorMixin`).
    Por isso o gate inclui apenas `leader` e `treasurer` alem de Pastor/Secretario.
    """

    required_roles = ('pastor', 'secretary', 'leader', 'treasurer')


class ScopedFileQuerysetMixin:
    """Camada de queryset: escopo por contexto dos arquivos (P-ARQ-08, RN-003a).

    `FileAsset` nao tem FK de contexto — o vinculo e o par string
    (`related_model`, `related_object_id`) (TECH_SPEC §5.8). Por isso o escopo de
    cada papel vira um predicado sobre esses dois campos, derivado dos MESMOS
    vinculos de lideranca que os `ScopedTo*` mixins do core usam nas outras listas:

    - Pastor / Secretario: veem TODOS os arquivos do tenant (curto-circuito —
      espelha `ScopedToCommunityMixin`/`ScopedToMinistryMixin`).
    - Lider (papel `leader`): cobre tanto Lider de Comunidade quanto Coordenador de
      Ministerio (nao ha papel `coordinator` em `User.Role`; a distincao e por qual
      entidade o vincula — mesma convencao de `schedules.PastorOrCoordinatorMixin`).
      Logo, um `leader` enxerga a UNIAO de:
        * arquivos `related_model='community'` cujas comunidades ele LIDERA
          (`Community.objects.filter(leaders__user_id=user.id)`, mesma fonte do
          lookup `leaders__user_id` usado em communities/people);
        * arquivos `related_model='ministry'` cujos ministerios ele COORDENA
          (`Ministry.objects.filter(coordinators__user_id=user.id)`, lookup
          `coordinators__user_id`).
    - Tesoureiro: arquivos de contexto financeiro (`related_model='finance'`).

    Multi-role (RN-003a): o escopo final e a UNIAO dos predicados de cada papel do
    usuario — quem e `['leader', 'treasurer']` ve os arquivos das suas comunidades/
    ministerios MAIS os financeiros. Implementado como OR de `Q`s.

    `related_object_id` e CharField; os ids de Community/Ministry sao castados para
    str antes do `__in`. Se um papel escopado nao tem nenhum vinculo, seu predicado
    nao casa com nada (lista vazia em `__in`), e ele simplesmente nao soma arquivos.
    """

    def get_scoped_file_queryset(self):
        user = self.request.user
        base = FileAsset.objects.all()

        if user.has_any_role('pastor', 'secretary'):
            return base

        predicate = Q()
        if user.has_any_role('leader'):
            community_ids = self._led_community_ids(user)
            predicate |= Q(
                related_model=CONTEXT_COMMUNITY,
                related_object_id__in=community_ids,
            )
            ministry_ids = self._coordinated_ministry_ids(user)
            predicate |= Q(
                related_model=CONTEXT_MINISTRY,
                related_object_id__in=ministry_ids,
            )
        if user.has_any_role('treasurer'):
            predicate |= Q(related_model=CONTEXT_FINANCE)

        # Sem nenhum papel escopado com vinculo: Q() vazio casaria com TUDO, o que
        # vazaria intra-tenant. Forcamos queryset vazio nesse caso (mais conservador).
        if not predicate:
            return base.none()
        return base.filter(predicate)

    @staticmethod
    def _led_community_ids(user):
        from apps.communities.models import Community

        return [
            str(pk)
            for pk in Community.objects.filter(leaders__user_id=user.id).values_list(
                'pk', flat=True
            )
        ]

    @staticmethod
    def _coordinated_ministry_ids(user):
        from apps.ministries.models import Ministry

        return [
            str(pk)
            for pk in Ministry.objects.filter(
                coordinators__user_id=user.id
            ).values_list('pk', flat=True)
        ]


class FileAssetListView(
    TenantRequiredMixin, FileAccessRoleMixin, ScopedFileQuerysetMixin, ListView
):
    """Lista arquivos do tenant, escopados por papel/contexto (ACCESS_MATRIX §3.8).

    Escopo de papel: ver `ScopedFileQuerysetMixin` (Pastor/Secretario veem tudo;
    Lider/Coordenador/Tesoureiro so o proprio contexto).

    Filtros (querystring), SEMPRE aplicados DENTRO do escopo do papel — um filtro
    nunca amplia o que o papel restringe (P-ARQ-08):
    - `?related_model=community&related_object_id=<id>`: arquivos de um contexto
      especifico (Pessoa/Comunidade/Ministerio). Como o filtro intersecta o
      queryset ja escopado, pedir um contexto fora do escopo retorna vazio (nao
      vaza).
    """

    template_name = 'files/file_list.html'
    context_object_name = 'file_assets'
    paginate_by = 25

    def get_queryset(self):
        qs = self.get_scoped_file_queryset()
        params = self.request.GET
        if related_model := params.get('related_model'):
            qs = qs.filter(related_model=related_model)
        if related_object_id := params.get('related_object_id'):
            qs = qs.filter(related_object_id=related_object_id)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = self.request.GET
        return context


class FileDownloadView(
    TenantRequiredMixin,
    FileAccessRoleMixin,
    ScopedFileQuerysetMixin,
    SingleObjectMixin,
    View,
):
    """Faz streaming dos bytes de um `FileAsset` do tenant atual (OD-021).

    Bloco 4 fecha a pendencia "(autorizado)" do Bloco 3: o queryset agora e o
    `get_scoped_file_queryset()` — um Lider so alcanca arquivos da(s) sua(s)
    comunidade(s); fora do escopo (ou cross-tenant/inexistente) =>
    `SingleObjectMixin.get_object` levanta Http404 (NUNCA 403, RISK-001).
    Pastor/Secretario continuam baixando qualquer arquivo do tenant.
    """

    model = FileAsset
    context_object_name = 'file_asset'

    def get_queryset(self):
        return self.get_scoped_file_queryset()

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


class FileDeleteView(TenantRequiredMixin, PastorRequiredMixin, DeleteView):
    """Exclui um `FileAsset` — APENAS Pastor (ACCESS_MATRIX §3.8, resolvido
    2026-06-05 a favor da matriz; Secretario NAO exclui).

    POST-only no efeito (DeleteView). O `FileAsset` e resolvido no schema do tenant
    atual (TENANT-04); cross-tenant ou inexistente => Http404 (RISK-001). Aqui NAO
    aplicamos o escopo fino por contexto: a barreira de papel ja e Pastor-only, e o
    Pastor enxerga todos os arquivos da sua igreja.

    Auditoria: a exclusao dispara AuditLog 'delete' automatico (FileAsset herda
    AuditLogMixin; receivers globais do core). Nao ha event_type de SecurityLog
    dedicado a exclusao de arquivo em `SecurityLog.EVENT_CHOICES`; por decisao da
    task NAO criamos migration — o AuditLog 'delete' cobre a trilha.
    """

    model = FileAsset
    template_name = 'files/file_confirm_delete.html'
    context_object_name = 'file_asset'
    success_url = reverse_lazy('files:list')

    def form_valid(self, form):
        messages.success(self.request, 'Arquivo excluido.')
        return super().form_valid(form)


class FileUploadView(TenantRequiredMixin, PastorOrSecretaryMixin, FormView):
    """Envia um arquivo (RF-065/067 · ACCESS_MATRIX §3.8) — Pastor/Secretario.

    Upload geral e Pastor-only na matriz; Secretario age como Pastor (OD-019), por
    isso `PastorOrSecretaryMixin`. O upload ESCOPADO de Lider/Coordenador (so a sua
    comunidade/ministerio) fica para o Comunidades v2 (escopo fino).

    A validacao pesada (MIME real via magic, tamanho <=10MB, sem SVG) e a auditoria
    (`sensitive_file_upload`) vivem em `services.upload_file` desde a Sprint 6 — aqui
    so traduzimos o form e tratamos o `ValidationError` (pt-BR) de volta na tela.
    """

    form_class = FileUploadForm
    template_name = 'files/file_upload_form.html'
    success_url = reverse_lazy('files:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pastor/Secretario escolhem qualquer contexto do tenant atual (TENANT-04).
        kwargs['communities'] = Community.objects.order_by('name')
        kwargs['ministries'] = Ministry.objects.order_by('name')
        return kwargs

    def form_valid(self, form):
        related_model, related_object_id = form.related()
        try:
            services.upload_file(
                uploaded_file=form.cleaned_data['file'],
                uploaded_by_id=self.request.user.id,
                related_model=related_model,
                related_object_id=related_object_id,
            )
        except ValidationError as exc:
            form.add_error('file', exc.messages[0])
            return self.form_invalid(form)
        messages.success(self.request, 'Arquivo enviado com sucesso.')
        return super().form_valid(form)
