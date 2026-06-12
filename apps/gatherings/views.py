"""Views de Encontro — CRUD tenant-scoped (ACCESS_MATRIX §3.6 / Sprint 4 Frente 1).

Papéis (§3.6 + OD-019; Secretário = admin como Pastor, sem excluir):
- Listar/Detalhe: Pastor/Secretário/Líder/Coordenador veem TODOS os encontros.
- Criar: barreira de papel ampla (`LeaderOrPastorMixin`); a barreira FINA por
  tipo×escopo vive no service (`create_gathering`) e no form (dropdown filtrado).
- Editar: Pastor/Secretário (qualquer) + Líder/Coordenador escopado (criador OU
  comunidade que lidera) via `GatheringEditScopeMixin`.
- Excluir: só Pastor (`PastorRequiredMixin`) — ação destrutiva (§3.6 🔒).

`created_by` (user_id do criador, TENANT-04) é gravado pelo service e alimenta a
trava "editar pelo criador".
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.mixins import (
    LeaderOrPastorMixin,
    PastorOrSecretaryMixin,
    PastorRequiredMixin,
    TenantRequiredMixin,
)
from apps.dashboard.views import calendar_context
from apps.gatherings import services
from apps.gatherings.forms import GatheringForm
from apps.gatherings.models import Gathering


class GatheringEditScopeMixin:
    """Camada de queryset da EDIÇÃO (§3.6): Pastor/Secretário veem tudo; Líder/
    Coordenador só o que criaram OU encontros de uma comunidade que lideram.

    Aplica-se só a editar (não a listar/ver — onde todos veem tudo). Fora do
    escopo → 404 (não vaza existência). Vínculos por `user_id` (TENANT-04).
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.has_any_role('pastor', 'secretary'):
            return qs
        return qs.filter(
            Q(created_by=user.id) | Q(community__leaders__user_id=user.id)
        ).distinct()


def _agenda_context(request):
    """Contexto da "Agenda do mês" de Encontros (RF-102 / item 4): a grade do
    calendário (reusa `calendar_context` do dashboard) + a lista dos encontros do mês
    exibido (`gatherings_in_month`). Compartilhado entre a `GatheringListView` (render
    inicial) e a `GatheringCalendarView` (fragmento de troca de mês)."""
    context = calendar_context(request)
    context['month_gatherings'] = services.gatherings_in_month(
        year=context['calendar_year'], month=context['calendar_month']
    )
    return context


class GatheringListView(TenantRequiredMixin, LeaderOrPastorMixin, ListView):
    """Lista todos os encontros da igreja (§3.6 — Líder/Coord também veem todos)."""

    model = Gathering
    template_name = 'gatherings/gathering_list.html'
    context_object_name = 'gatherings'
    paginate_by = 25

    def get_queryset(self):
        qs = Gathering.objects.select_related('community').order_by('-date')
        if gtype := self.request.GET.get('type'):
            qs = qs.filter(gathering_type=gtype)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['type_choices'] = Gathering.Type.choices
        context['filters'] = self.request.GET
        # Analytics da tela (RF-120): cards + linha de presença (church-wide, §3.6).
        context['stats'] = services.gatherings_page_stats()
        # Agenda do mês (RF-102) — calendário (só pontos) + lista lateral dos
        # encontros do mês. A navegação de mês é servida por `GatheringCalendarView`.
        context.update(_agenda_context(self.request))
        return context


class GatheringCalendarView(TenantRequiredMixin, LeaderOrPastorMixin, TemplateView):
    """Fragmento da "Agenda do mês" (RF-102) — troca de mês via HTMX na tela de
    Encontros. Devolve `_calendar_agenda.html` (calendário + lista) para o swap do
    bloco `#enc-calendar`. Mesmo gate de papel da lista (§3.6)."""

    template_name = 'gatherings/_calendar_agenda.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_agenda_context(self.request))
        return context


class GatheringDetailView(TenantRequiredMixin, LeaderOrPastorMixin, DetailView):
    """Detalhe de um encontro (todos os papéis de gestão veem qualquer um, §3.6)."""

    model = Gathering
    template_name = 'gatherings/gathering_detail.html'
    context_object_name = 'gathering'

    def get_queryset(self):
        return Gathering.objects.select_related('community')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['present_count'] = self.object.attendances.filter(
            is_present=True
        ).count()
        context['can_mark'] = services.can_mark_attendance(
            self.request.user, self.object
        )
        return context


class GatheringCreateView(TenantRequiredMixin, PastorOrSecretaryMixin, CreateView):
    """Cria encontro — APENAS Pastor/Secretário (RN-018 · Comunidades v2).

    Mudança da regra anterior (§3.6 deixava o Líder criar): a criação de encontros é
    administrativa. O service `create_gathering` reforça a trava (defesa em
    profundidade, P-ARQ-08). Não chamamos `super().form_valid` (faria form.save(),
    pulando o service e o `created_by`).
    """

    model = Gathering
    form_class = GatheringForm
    template_name = 'gatherings/gathering_form.html'
    success_url = reverse_lazy('gatherings:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['church'] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            services.create_gathering(
                church=self.request.tenant,
                user=self.request.user,
                gathering_type=data['gathering_type'],
                date=data['date'],
                title=data.get('title') or None,
                community=data.get('community'),
                description=data.get('description', ''),
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)
        messages.success(self.request, 'Encontro criado com sucesso.')
        # NÃO chamamos super().form_valid (faria form.save(), pulando o service
        # e o created_by).
        return redirect(self.success_url)


class GatheringUpdateView(
    TenantRequiredMixin, LeaderOrPastorMixin, GatheringEditScopeMixin, UpdateView
):
    """Edita encontro. Pastor/Secretário (qualquer) + Líder/Coord escopado.

    O tipo é travado no form (não-conversível); a comunidade só aparece em
    encontros COMMUNITY e é escopada. AuditLog automático (AuditLogMixin).
    """

    model = Gathering
    form_class = GatheringForm
    template_name = 'gatherings/gathering_form.html'

    def get_success_url(self):
        return reverse_lazy('gatherings:detail', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['church'] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Encontro atualizado com sucesso.')
        return super().form_valid(form)


class GatheringDeleteView(TenantRequiredMixin, PastorRequiredMixin, DeleteView):
    """Exclui encontro (hard delete). Só Pastor (§3.6 🔒). AuditLog automático."""

    model = Gathering
    template_name = 'gatherings/gathering_confirm_delete.html'
    success_url = reverse_lazy('gatherings:list')

    def form_valid(self, form):
        messages.success(self.request, 'Encontro excluido.')
        return super().form_valid(form)


class AttendanceMarkView(TenantRequiredMixin, LeaderOrPastorMixin, View):
    """Marca presença em lote num encontro (RF-040 / RN-009 / §3.6).

    Barreira de papel ampla (`LeaderOrPastorMixin`) + barreira FINA por encontro
    (`services.can_mark_attendance`): Pastor/Secretário marcam em qualquer; Líder/
    Coordenador só no que criaram ou na comunidade que lideram. Fora do escopo →
    404 (não vaza a existência do encontro).

    GET: roster (membros da comunidade ou pessoas ativas) com os já-presentes
    pré-marcados. POST: `update_or_create` por pessoa (nunca duplica).
    """

    def _get_gathering(self, request, pk):
        # Sem select_related('community'): a comunidade só é tocada (uma vez) quando
        # o encontro tem uma — eager load incondicional seria desnecessário p/
        # encontros sem comunidade (nplusone reclamaria). Não há laço aqui.
        gathering = get_object_or_404(Gathering, pk=pk)
        if not services.can_mark_attendance(request.user, gathering):
            raise Http404()
        return gathering

    def get(self, request, pk):
        gathering = self._get_gathering(request, pk)
        roster = services.attendance_roster(gathering)
        present_ids = set(
            gathering.attendances.filter(is_present=True).values_list(
                'person_id', flat=True
            )
        )
        return render(
            request,
            'gatherings/attendance_mark.html',
            {'gathering': gathering, 'roster': roster, 'present_ids': present_ids},
        )

    def post(self, request, pk):
        gathering = self._get_gathering(request, pk)
        present_ids = [int(pid) for pid in request.POST.getlist('present')]
        count = services.mark_attendance_bulk(
            gathering=gathering, present_person_ids=present_ids
        )
        messages.success(request, f'Presenca registrada: {count} presente(s).')
        return redirect('gatherings:detail', pk=gathering.pk)
