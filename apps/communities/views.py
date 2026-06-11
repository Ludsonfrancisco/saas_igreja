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
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
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
from apps.gatherings import services as gathering_services
from apps.gatherings.models import AttendanceSession, Gathering


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
    """Lista de comunidades ESCOPADA por papel (RF-106 · Comunidades v2): Pastor/
    Secretário veem todas; o Líder vê só a(s) célula(s) que lidera."""

    model = Community
    template_name = 'communities/community_list.html'
    context_object_name = 'communities'

    def get_queryset(self):
        qs = Community.objects.prefetch_related('leaders').order_by('name')
        user = self.request.user
        if user.has_any_role('pastor', 'secretary'):
            return qs
        # Líder: só as células que lidera (vínculo por user_id, TENANT-04).
        return qs.filter(leaders__user_id=user.id).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Frequência por célula (RF-109) numa query só (sem N+1); anexa a cada objeto.
        communities = list(context['communities'])
        freqs = gathering_services.cell_frequencies(communities)
        for community in communities:
            community.freq = freqs.get(community.pk)
        context['communities'] = communities
        return context


class CommunityDetailView(
    CommunitiesEnabledMixin,
    TenantRequiredMixin,
    LeaderOrPastorMixin,
    ScopedToCommunityMixin,
    DetailView,
):
    """Detalhe da célula. Pastor vê qualquer; Líder só a que lidera (fora → 404).

    Mostra os "dias a lançar" (RF-107) e o card de frequência (RF-109)."""

    model = Community
    template_name = 'communities/community_detail.html'
    context_object_name = 'community'
    # default community_scope_lookup = 'leaders__user_id' (queryset de Community)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_days'] = gathering_services.cell_pending_days(self.object)
        context['frequency'] = gathering_services.cell_attendance_summary(self.object)
        return context


class CommunitySessionView(
    CommunitiesEnabledMixin, TenantRequiredMixin, LeaderOrPastorMixin, View
):
    """Lançamento de presença de uma reunião da célula (RF-108 · Comunidades v2).

    Líder da célula (ou Pastor/Secretário) marca presente/falta dos membros, adiciona
    visitante (só o nome) e a anotação do dia, e confirma. Escopo: a comunidade tem
    de ser a do Líder (admin vê todas) e o encontro tem de ser COMMUNITY daquela
    célula — fora disso → 404 (não vaza)."""

    def _resolve(self, request, pk, gathering_pk):
        cqs = Community.objects.all()
        if not request.user.has_any_role('pastor', 'secretary'):
            cqs = cqs.filter(leaders__user_id=request.user.id)
        community = get_object_or_404(cqs, pk=pk)
        gathering = get_object_or_404(
            Gathering,
            pk=gathering_pk,
            gathering_type=Gathering.Type.COMMUNITY,
            community=community,
        )
        return community, gathering

    def get(self, request, pk, gathering_pk):
        community, gathering = self._resolve(request, pk, gathering_pk)
        roster = gathering_services.attendance_roster(gathering)
        present_ids = set(
            gathering.attendances.filter(is_present=True).values_list(
                'person_id', flat=True
            )
        )
        session = AttendanceSession.objects.filter(gathering=gathering).first()
        return render(
            request,
            'communities/community_session.html',
            {
                'community': community,
                'gathering': gathering,
                'roster': roster,
                'present_ids': present_ids,
                'note': session.note if session else '',
            },
        )

    def post(self, request, pk, gathering_pk):
        community, gathering = self._resolve(request, pk, gathering_pk)
        present_ids = [int(pid) for pid in request.POST.getlist('present')]
        visitor_names = request.POST.get('visitors', '').splitlines()
        gathering_services.launch_attendance_session(
            gathering=gathering,
            present_person_ids=present_ids,
            visitor_names=visitor_names,
            note=request.POST.get('note', ''),
            confirmed_by_id=request.user.id,
        )
        messages.success(request, 'Presença da célula registrada.')
        return redirect('communities:detail', pk=community.pk)


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
