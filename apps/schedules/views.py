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

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
)

from apps.core.mixins import (
    LeaderOrPastorMixin,
    RoleRequiredMixin,
    ScopedToMinistryMixin,
    TenantRequiredMixin,
)
from apps.schedules import services
from apps.schedules.forms import ScheduleExceptionForm, ScheduleForm
from apps.schedules.models import Schedule

SCHEDULE_SCOPE_LOOKUP = 'ministry__coordinators__user_id'


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
