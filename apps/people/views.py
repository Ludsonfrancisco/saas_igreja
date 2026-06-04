"""Views de Pessoa — CRUD tenant-scoped (ACCESS_MATRIX §3.3).

Papéis (Frente 3 Bloco 1): Listar/Ver/Editar são `LeaderOrPastorMixin` +
`ScopedToCommunityMixin` — Pastor vê tudo, Líder só as pessoas da(s) comunidade(s)
que lidera (lookup `community__leaders__user_id`, M2M OD-019). Criar e as ações
LGPD (anonimizar/exportar) seguem `PastorRequiredMixin`. (Secretário entra no
bloco de Gestão de Acessos.)

Toda mutação passa pelo SERVICE (`apps.people.services`), nunca por `form.save()`:
é lá que vivem as barreiras de consentimento (OPS-05) e limite de plano (OPS-04).
A view só traduz o checkbox `consent_given` em `consent_given_at`.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, ListView, UpdateView

from apps.communities.models import Community
from apps.core.mixins import (
    LeaderOrPastorMixin,
    PastorOrSecretaryMixin,
    PastorRequiredMixin,
    ScopedToCommunityMixin,
    TenantRequiredMixin,
)
from apps.ministries.models import Ministry
from apps.people import services
from apps.people.forms import PersonForm
from apps.people.models import Person


class PersonListView(
    TenantRequiredMixin, LeaderOrPastorMixin, ScopedToCommunityMixin, ListView
):
    """Lista pessoas ATIVAS com filtros e busca. Pastor vê todas; Líder só as da
    sua comunidade (ACCESS_MATRIX §3.3).

    O escopo de papel vem do `ScopedToCommunityMixin` (`super().get_queryset()`):
    para Pessoa, o lookup é `community__leaders__user_id` (a pessoa pertence a uma
    comunidade cujo líder é o user logado). Pastor curto-circuita e vê tudo.
    Exclui anonimizadas; filtros `status`/`community`/`ministry`; busca `q`.
    """

    model = Person
    template_name = 'people/person_list.html'
    context_object_name = 'persons'
    paginate_by = 25
    community_scope_lookup = 'community__leaders__user_id'

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .filter(anonymized_at__isnull=True)
            .select_related('community')
        )
        params = self.request.GET
        if status := params.get('status'):
            qs = qs.filter(status=status)
        if community := params.get('community'):
            qs = qs.filter(community_id=community)
        if ministry := params.get('ministry'):
            qs = qs.filter(ministries__id=ministry)
        if search := params.get('q'):
            qs = qs.filter(name__icontains=search)
        return qs.order_by('name').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Person.Status.choices
        context['communities'] = Community.objects.all()
        context['ministries'] = Ministry.objects.all()
        context['filters'] = self.request.GET
        return context


class PersonDetailView(
    TenantRequiredMixin, LeaderOrPastorMixin, ScopedToCommunityMixin, DetailView
):
    """Detalhe de uma pessoa. Pastor vê qualquer uma; Líder só as da sua comunidade
    (fora do escopo → 404, sem vazar existência). ACCESS_MATRIX §3.3."""

    model = Person
    template_name = 'people/person_detail.html'
    context_object_name = 'person'
    community_scope_lookup = 'community__leaders__user_id'


class PersonCreateView(TenantRequiredMixin, PastorOrSecretaryMixin, FormView):
    """Cadastra pessoa via service (consent + limite de plano). Pastor ou Secretário."""

    template_name = 'people/person_form.html'
    form_class = PersonForm
    success_url = reverse_lazy('people:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['church'] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        linked = data.get('linked_user')
        try:
            services.create_person(
                church=self.request.tenant,
                name=data['name'],
                status=data['status'],
                email=data['email'] or None,
                phone=data['phone'] or None,
                birth_date=data['birth_date'],
                community=data['community'],
                ministries=data['ministries'],
                consent_given_at=timezone.now() if data['consent_given'] else None,
                notes=data['notes'],
                user_id=linked.id if linked else None,
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)
        messages.success(self.request, 'Pessoa cadastrada com sucesso.')
        return super().form_valid(form)


class PersonUpdateView(
    TenantRequiredMixin, LeaderOrPastorMixin, ScopedToCommunityMixin, UpdateView
):
    """Edita uma pessoa via service. Pastor edita qualquer uma; Líder só as da sua
    comunidade (ACCESS_MATRIX §3.3). Revalida consent."""

    model = Person
    form_class = PersonForm
    template_name = 'people/person_form.html'
    community_scope_lookup = 'community__leaders__user_id'

    def get_success_url(self):
        return reverse_lazy('people:detail', kwargs={'pk': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['church'] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        data = form.cleaned_data
        linked = data.get('linked_user')
        # Preserva o consentimento original; só (re)marca/limpa conforme o checkbox.
        consent_at = self.object.consent_given_at
        if data['consent_given'] and consent_at is None:
            consent_at = timezone.now()
        elif not data['consent_given']:
            consent_at = None
        try:
            services.update_person(
                person=self.object,
                name=data['name'],
                status=data['status'],
                email=data['email'] or None,
                phone=data['phone'] or None,
                birth_date=data['birth_date'],
                community=data['community'],
                consent_given_at=consent_at,
                notes=data['notes'],
                ministries=data['ministries'],
                user_id=linked.id if linked else None,
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)
        messages.success(self.request, 'Pessoa atualizada com sucesso.')
        # NÃO chamamos super().form_valid (faria form.save(), pulando o service).
        return redirect(self.get_success_url())


class PersonAnonymizeView(TenantRequiredMixin, PastorRequiredMixin, View):
    """Anonimização LGPD com DUPLA confirmação (OD-014). POST-only no efeito.

    Ação IRREVERSÍVEL (soft delete + purge físico em 30 dias). A barreira escolhida
    (OD-014, opção b): o Pastor precisa DIGITAR o nome exato da pessoa para
    confirmar. GET mostra o formulário de confirmação; POST só anonimiza se o nome
    digitado bate com `person.name`. Apenas Pastor (ACCESS_MATRIX §3.3).
    """

    def get(self, request, pk):
        person = get_object_or_404(Person, pk=pk, anonymized_at__isnull=True)
        return render(request, 'people/person_anonymize.html', {'person': person})

    def post(self, request, pk):
        person = get_object_or_404(Person, pk=pk, anonymized_at__isnull=True)
        typed = request.POST.get('confirm_name', '').strip()
        if typed != person.name:
            messages.error(
                request,
                'O nome digitado nao confere. Anonimizacao cancelada.',
            )
            return redirect('people:anonymize', pk=person.pk)
        services.anonymize_person(person=person)
        messages.success(request, 'Pessoa anonimizada (LGPD).')
        return redirect('people:list')


class PersonExportView(TenantRequiredMixin, PastorRequiredMixin, View):
    """Exporta os dados de uma pessoa como download (JSON ou CSV). Apenas Pastor.

    `?format=csv` baixa CSV; qualquer outro valor baixa JSON. O service registra
    AuditLog('export') + SecurityLog `person_exported` (RN-005).
    """

    def get(self, request, pk):
        person = get_object_or_404(Person, pk=pk)
        result = services.export_person_data(person=person)
        if request.GET.get('format') == 'csv':
            response = HttpResponse(result['csv'], content_type='text/csv')
            filename = f'pessoa_{person.pk}.csv'
        else:
            response = HttpResponse(result['json'], content_type='application/json')
            filename = f'pessoa_{person.pk}.json'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
