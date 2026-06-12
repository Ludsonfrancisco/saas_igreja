"""Views de Ministério — CRUD tenant-scoped (ACCESS_MATRIX §3.5 / Frente 3 Bloco 3).

Papéis (OD-019; Secretário entra no bloco de Gestão de Acessos):
- Listar/Detalhe: Pastor + Líder/Coordenador (todos veem todos os ministérios).
- Editar: Pastor (qualquer) + Coordenador escopado (só o que coordena).
- Criar/Excluir: apenas Pastor.
- Definir coordenadores (M2M): apenas Pastor — para o Coordenador o campo some.

Sem service/limite de plano (ministério não tem teto de plano nem gate de
`has_communities`); a auditoria é automática via `AuditLogMixin`.
"""

from django.contrib import messages
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.core.mixins import (
    LeaderOrPastorMixin,
    PastorOrSecretaryMixin,
    PastorRequiredMixin,
    ScopedToMinistryMixin,
    TenantRequiredMixin,
)
from apps.ministries import services
from apps.ministries.forms import MinistryForm
from apps.ministries.models import Ministry


class MinistryListView(TenantRequiredMixin, LeaderOrPastorMixin, ListView):
    """Lista TODOS os ministérios (Pastor e Líder/Coordenador veem todos; §3.5)."""

    model = Ministry
    template_name = 'ministries/ministry_list.html'
    context_object_name = 'ministries'

    def get_queryset(self):
        # `members_count` (RF-124 design): nº de voluntários por ministério anotado no
        # banco (sem N+1), p/ o card. `coordinators` prefetch p/ os avatares.
        return (
            Ministry.objects.prefetch_related('coordinators')
            .annotate(
                members_count=Count(
                    'members',
                    filter=Q(members__anonymized_at__isnull=True),
                    distinct=True,
                )
            )
            .order_by('name')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Analytics da tela (RF-121): cards + barra de GAP (church-wide, §3.5).
        context['stats'] = services.ministries_page_stats()
        return context


class MinistryDetailView(TenantRequiredMixin, LeaderOrPastorMixin, DetailView):
    """Detalhe de um ministério (todos os líderes/coordenadores podem ver; §3.5)."""

    model = Ministry
    template_name = 'ministries/ministry_detail.html'
    context_object_name = 'ministry'


class MinistryCreateView(TenantRequiredMixin, PastorOrSecretaryMixin, CreateView):
    """Cria ministério. Pastor ou Secretário. AuditLog automático (AuditLogMixin)."""

    model = Ministry
    form_class = MinistryForm
    template_name = 'ministries/ministry_form.html'
    success_url = reverse_lazy('ministries:list')

    def form_valid(self, form):
        messages.success(self.request, 'Ministerio criado com sucesso.')
        return super().form_valid(form)


class MinistryUpdateView(
    TenantRequiredMixin, LeaderOrPastorMixin, ScopedToMinistryMixin, UpdateView
):
    """Edita ministério. Pastor (qualquer) + Coordenador escopado (só o seu)."""

    model = Ministry
    form_class = MinistryForm
    template_name = 'ministries/ministry_form.html'

    def get_success_url(self):
        return reverse_lazy('ministries:detail', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pastor e Secretário definem coordenadores (§3.5); p/ o Coordenador some.
        kwargs['can_set_coordinators'] = self.request.user.has_any_role(
            'pastor', 'secretary'
        )
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Ministerio atualizado com sucesso.')
        return super().form_valid(form)


class MinistryDeleteView(TenantRequiredMixin, PastorRequiredMixin, DeleteView):
    """Exclui ministério (hard delete). Apenas Pastor. AuditLog automático."""

    model = Ministry
    template_name = 'ministries/ministry_confirm_delete.html'
    success_url = reverse_lazy('ministries:list')

    def form_valid(self, form):
        messages.success(self.request, 'Ministerio excluido.')
        return super().form_valid(form)
