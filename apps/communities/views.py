"""Views de Comunidade — CRUD tenant-scoped (ACCESS_MATRIX §3.4 / Frente 3 Bloco 2).

Papéis (OD-019; Secretário entra no bloco de Gestão de Acessos):
- Listar: Pastor + Líder (todas as comunidades).
- Detalhe/Editar: Pastor (qualquer) + Líder escopado (só a que lidera).
- Criar/Excluir: apenas Pastor.
- Definir líderes (M2M): apenas Pastor — para o Líder, o campo some no form.

Todo o módulo é escondido quando a igreja não usa comunidades
(`has_communities=False`) via `CommunitiesEnabledMixin` (404).
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.communities import services
from apps.communities.forms import CommunityForm
from apps.communities.models import Community
from apps.core.mixins import (
    LeaderOrPastorMixin,
    PastorOrSecretaryMixin,
    PastorRequiredMixin,
    ScopedToCommunityMixin,
    TenantRequiredMixin,
)


class CommunitiesEnabledMixin:
    """404 quando a igreja não usa comunidades (`has_communities=False`).

    Esconde o módulo inteiro de forma conservadora — nem revela as rotas.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.tenant.has_communities:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)


class CommunityListView(
    CommunitiesEnabledMixin, TenantRequiredMixin, LeaderOrPastorMixin, ListView
):
    """Lista TODAS as comunidades (Pastor e Líder veem todas; §3.4)."""

    model = Community
    template_name = 'communities/community_list.html'
    context_object_name = 'communities'

    def get_queryset(self):
        return Community.objects.prefetch_related('leaders').order_by('name')


class CommunityDetailView(
    CommunitiesEnabledMixin,
    TenantRequiredMixin,
    LeaderOrPastorMixin,
    ScopedToCommunityMixin,
    DetailView,
):
    """Detalhe. Pastor vê qualquer; Líder só a que lidera (fora do escopo → 404)."""

    model = Community
    template_name = 'communities/community_detail.html'
    context_object_name = 'community'
    # default community_scope_lookup = 'leaders__user_id' (queryset de Community)


class CommunityCreateView(
    CommunitiesEnabledMixin, TenantRequiredMixin, PastorOrSecretaryMixin, CreateView
):
    """Cria comunidade via service (plano + has_communities). Pastor ou Secretário."""

    model = Community
    form_class = CommunityForm
    template_name = 'communities/community_form.html'
    success_url = reverse_lazy('communities:list')

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            services.create_community(
                church=self.request.tenant,
                name=data['name'],
                leaders=data.get('leaders'),
                meeting_day=data['meeting_day'] or None,
                meeting_time=data['meeting_time'],
                is_active=data['is_active'],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)
        messages.success(self.request, 'Comunidade criada com sucesso.')
        # NÃO chamamos super().form_valid (faria form.save(), pulando o service).
        return redirect(self.success_url)


class CommunityUpdateView(
    CommunitiesEnabledMixin,
    TenantRequiredMixin,
    LeaderOrPastorMixin,
    ScopedToCommunityMixin,
    UpdateView,
):
    """Edita comunidade. Pastor (qualquer) + Líder escopado. AuditLog automático."""

    model = Community
    form_class = CommunityForm
    template_name = 'communities/community_form.html'

    def get_success_url(self):
        return reverse_lazy('communities:detail', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pastor e Secretário definem líderes (§3.4); para o Líder o campo some.
        kwargs['can_set_leaders'] = self.request.user.has_any_role(
            'pastor', 'secretary'
        )
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Comunidade atualizada com sucesso.')
        return super().form_valid(form)


class CommunityDeleteView(
    CommunitiesEnabledMixin, TenantRequiredMixin, PastorRequiredMixin, DeleteView
):
    """Exclui comunidade (hard delete). Só Pastor. AuditLog automático (post_delete)."""

    model = Community
    template_name = 'communities/community_confirm_delete.html'
    success_url = reverse_lazy('communities:list')

    def form_valid(self, form):
        messages.success(self.request, 'Comunidade excluida.')
        return super().form_valid(form)
