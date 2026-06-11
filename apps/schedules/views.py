"""Views de Escala — CRUD tenant-scoped (ACCESS_MATRIX §3.7 / Sprint 5 Frente 1).

Papéis (§3.7 + decisão Sprint 5):
- Pastor/Secretário: CRUD em qualquer ministério (admin).
- Coordenador: CRUD só no seu ministério (`ScopedToMinistryMixin`, lookup
  `ministry__coordinators__user_id`). Líder de comunidade (papel `leader` sem
  coordenação) cai no escopo vazio — não vê nem cria nada.
- Aprovar exceção de conflito: Frente 2 (Pastor + Coordenador competente; o
  Secretário NÃO aprova).

A barreira de PAPEL é ampla (`LeaderOrPastorMixin`); o ESCOPO refina no queryset
(P-ARQ-08). Criar passa pelo service (`create_schedule`: vínculo + bloqueio de
conflito).
"""

from datetime import date

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
)

from apps.core.audit import log_security_event
from apps.core.mixins import (
    LeaderOrPastorMixin,
    RoleRequiredMixin,
    ScopedToMinistryMixin,
    TenantRequiredMixin,
)
from apps.gatherings.models import Gathering
from apps.schedules import services
from apps.schedules.forms import ScheduleExceptionForm, ScheduleForm
from apps.schedules.models import Schedule
from apps.schedules.tokens import read_volunteer_token

SCHEDULE_SCOPE_LOOKUP = 'ministry__coordinators__user_id'


def _open_day():
    """Dia configurável de abertura de pendências da igreja atual (RN-023)."""
    return getattr(connection.tenant, 'schedule_pending_open_day', 25)


def _event_modal_context(*, user, gathering):
    """Estado do modal de escalação (RF-112/113/114): para cada ministério do escopo
    do `user`, o roster, se deu opt-out neste evento e os direitos de opt-out.

    `can_optout` (marcar "não atuaremos") = só o coordenador do ministério (RN-022).
    `can_clear` (voltar a atuar) = coordenador OU Pastor/Secretário.
    """
    ministries = (
        services.coordinated_ministries(user)
        .order_by('name')
        .prefetch_related('members')  # evita N+1 no roster por ministério (P-ARQ-09)
    )
    opted_ids = set(
        gathering.ministry_optouts.filter(ministry__in=ministries).values_list(
            'ministry_id', flat=True
        )
    )
    is_admin = user.has_any_role('pastor', 'secretary')
    blocks = []
    for m in ministries:
        is_coordinator = m.coordinators.filter(user_id=user.id).exists()
        blocks.append(
            {
                'ministry': m,
                'opted_out': m.pk in opted_ids,
                'roster': services.ministry_roster(ministry=m, gathering=gathering),
                'can_optout': is_coordinator,
                'can_clear': is_coordinator or is_admin,
            }
        )
    return {'gathering': gathering, 'blocks': blocks}


class PastorOrCoordinatorMixin(RoleRequiredMixin):
    """Aprovação de exceção (§3.7): Pastor ou Coordenador (papel `leader`).

    O Secretário é EXCLUÍDO de propósito (decisão Sprint 5: admin no CRUD, mas não
    aprova exceção). A competência fina por ministério (Coordenador só o seu) é
    refinada no form (queryset de `ministry`) e revalidada no service
    (`is_competent_approver`) — defesa em profundidade (P-ARQ-08).
    """

    required_roles = ('pastor', 'leader')


class ScheduleListView(
    TenantRequiredMixin, LeaderOrPastorMixin, ScopedToMinistryMixin, ListView
):
    """Lista escalas. Pastor/Secretário todas; Coordenador só do seu ministério."""

    model = Schedule
    template_name = 'schedules/schedule_list.html'
    context_object_name = 'schedules'
    paginate_by = 25
    ministry_scope_lookup = SCHEDULE_SCOPE_LOOKUP

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related('ministry', 'person', 'gathering')
            .distinct()
        )


class ScheduleDetailView(
    TenantRequiredMixin, LeaderOrPastorMixin, ScopedToMinistryMixin, DetailView
):
    """Detalhe. Coordenador só do seu ministério (fora do escopo → 404)."""

    model = Schedule
    template_name = 'schedules/schedule_detail.html'
    context_object_name = 'schedule'
    ministry_scope_lookup = SCHEDULE_SCOPE_LOOKUP

    def get_queryset(self):
        return super().get_queryset().select_related('ministry', 'person', 'gathering')


class ScheduleCreateView(TenantRequiredMixin, LeaderOrPastorMixin, CreateView):
    """Cria escala via service (vínculo ao ministério + bloqueio de conflito §3.7)."""

    model = Schedule
    form_class = ScheduleForm
    template_name = 'schedules/schedule_form.html'
    success_url = reverse_lazy('schedules:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            services.create_schedule(
                ministry=data['ministry'],
                person=data['person'],
                gathering=data['gathering'],
                role=data['role'],
                notes=data['notes'],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)
        messages.success(self.request, 'Escala criada com sucesso.')
        # NÃO super().form_valid (faria form.save(), pulando o service/validações).
        return redirect(self.success_url)


class ScheduleUpdateView(
    TenantRequiredMixin, LeaderOrPastorMixin, ScopedToMinistryMixin, UpdateView
):
    """Edita `role`/`notes` (alocação travada). Coordenador só do seu ministério."""

    model = Schedule
    form_class = ScheduleForm
    template_name = 'schedules/schedule_form.html'
    ministry_scope_lookup = SCHEDULE_SCOPE_LOOKUP

    def get_success_url(self):
        return reverse_lazy('schedules:detail', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Escala atualizada com sucesso.')
        return super().form_valid(form)


class ScheduleDeleteView(
    TenantRequiredMixin, LeaderOrPastorMixin, ScopedToMinistryMixin, DeleteView
):
    """Exclui escala. Coordenador só do seu ministério (§3.7). AuditLog automático."""

    model = Schedule
    template_name = 'schedules/schedule_confirm_delete.html'
    success_url = reverse_lazy('schedules:list')
    ministry_scope_lookup = SCHEDULE_SCOPE_LOOKUP

    def form_valid(self, form):
        messages.success(self.request, 'Escala excluida.')
        return super().form_valid(form)


class ScheduleExceptionCreateView(
    TenantRequiredMixin, PastorOrCoordinatorMixin, FormView
):
    """Cria escala em conflito COM aprovação explícita (§3.7).

    Gate de papel = Pastor ou Coordenador (Secretário 403). O service
    (`approve_exception`) exige aprovador competente + justificativa + conflito
    real, registra `ScheduleConflictApproval` (AuditLog) e SecurityLog.
    """

    form_class = ScheduleExceptionForm
    template_name = 'schedules/schedule_exception_form.html'
    success_url = reverse_lazy('schedules:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        """Pré-preenche a partir do modal de escalação (RF-113 "escalar mesmo assim"):
        `?ministry=&person=&gathering=` viram o estado inicial do form."""
        initial = super().get_initial()
        for field in ('ministry', 'person', 'gathering'):
            value = self.request.GET.get(field)
            if value and value.isdigit():
                initial[field] = value
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            services.approve_exception(
                actor=self.request.user,
                ministry=data['ministry'],
                person=data['person'],
                gathering=data['gathering'],
                justification=data['justification'],
                role=data['role'],
                notes=data['notes'],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)
        messages.success(self.request, 'Excecao de conflito aprovada e escala criada.')
        return super().form_valid(form)


class ScheduleEventListView(TenantRequiredMixin, LeaderOrPastorMixin, View):
    """Escalas por evento (RF-111/115/117) — entrada principal coordenador-cêntrica.

    Lista os eventos da janela ativa (mês corrente + mês seguinte após o dia
    configurável) com badge de ministérios pendentes; painel das pendências do
    coordenador; KPIs no topo (RF-117 leve). O escopo (quais ministérios) vem do
    service `coordinated_ministries` (Pastor/Sec = todos).
    """

    template_name = 'schedules/schedule_events.html'

    def get(self, request):
        open_day = _open_day()
        events = services.events_with_pending(user=request.user, open_day=open_day)
        pending = [e for e in events if e['pending'] > 0]
        return render(
            request,
            self.template_name,
            {
                'events': events,
                'pending_events': pending,
                'kpi_total': len(events),
                'kpi_pending': len(pending),
                'kpi_done': len(events) - len(pending),
            },
        )


class ScheduleEventModalView(TenantRequiredMixin, LeaderOrPastorMixin, View):
    """Modal de escalação de um evento (RF-112/113). Fragmento HTMX.

    GET devolve o modal (roster por ministério do escopo). POST escala os voluntários
    marcados de um ministério (campo `ministry`, lista `person_ids`) via service e
    re-renderiza o modal atualizado.
    """

    template_name = 'schedules/_schedule_modal.html'

    def _gathering(self, pk):
        return get_object_or_404(Gathering, pk=pk)

    def get(self, request, pk):
        gathering = self._gathering(pk)
        return render(
            request,
            self.template_name,
            _event_modal_context(user=request.user, gathering=gathering),
        )

    def post(self, request, pk):
        gathering = self._gathering(pk)
        ministry = get_object_or_404(
            services.coordinated_ministries(request.user),
            pk=request.POST.get('ministry'),
        )
        person_ids = request.POST.getlist('person_ids')
        try:
            created, conflicted = services.schedule_members_bulk(
                ministry=ministry,
                gathering=gathering,
                person_ids=person_ids,
                actor=request.user,
            )
        except ValidationError as exc:
            raise Http404 from exc  # fora do escopo → não revela o evento
        ctx = _event_modal_context(user=request.user, gathering=gathering)
        ctx['feedback'] = {
            'created': created,
            'conflicted': [p.name for p in conflicted],
            'ministry': ministry.name,
        }
        return render(request, self.template_name, ctx)


class MinistryEventOptOutView(TenantRequiredMixin, LeaderOrPastorMixin, View):
    """Opt-out por ministério/evento (RF-114/RN-022). POST alterna; devolve o modal.

    `action=set` marca "não atuaremos"; `action=clear` remove. Escopo/competência
    revalidados no service (`set_optout`/`remove_optout`).
    """

    template_name = 'schedules/_schedule_modal.html'

    def post(self, request, pk, ministry_pk):
        gathering = get_object_or_404(Gathering, pk=pk)
        ministry = get_object_or_404(
            services.coordinated_ministries(request.user), pk=ministry_pk
        )
        try:
            if request.POST.get('action') == 'clear':
                services.remove_optout(
                    ministry=ministry, gathering=gathering, actor=request.user
                )
            else:
                services.set_optout(
                    ministry=ministry, gathering=gathering, actor=request.user
                )
        except ValidationError as exc:
            raise Http404 from exc
        return render(
            request,
            self.template_name,
            _event_modal_context(user=request.user, gathering=gathering),
        )


class VolunteerScheduleView(View):
    """Acesso READ-ONLY do voluntário às próprias escalas via magic-link (OD-022).

    Público (sem conta/login/MFA) e tenant-scoped pelo subdomínio — distinto do
    Membro geral (OD-004, sem acesso). O token (apps/schedules/tokens.py) carrega
    `person_id` + tenant; aqui revalidamos o tenant atual e exigimos pessoa
    existente e NÃO anonimizada (LGPD). Falha → página genérica 'link inválido'
    (não vaza existência). Mostra só as escalas FUTURAS da própria pessoa.
    """

    def get(self, request, token):
        from apps.people.models import Person

        person_id = read_volunteer_token(
            token,
            tenant=connection.schema_name,
            max_age=settings.VOLUNTEER_LINK_MAX_AGE,
        )
        person = None
        if person_id is not None:
            person = Person.objects.filter(
                pk=person_id, anonymized_at__isnull=True
            ).first()
        if person is None:
            return render(request, 'schedules/volunteer_invalid.html', status=404)

        log_security_event(
            event_type='volunteer_schedule_access',
            payload={'person_id': person.pk},
        )

        schedules = (
            person.schedules.filter(gathering__date__gte=date.today())
            .select_related('ministry', 'gathering')
            .order_by('gathering__date')
        )
        return render(
            request,
            'schedules/volunteer_schedule.html',
            {'person': person, 'schedules': schedules},
        )
