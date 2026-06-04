"""Views de Pessoa — CRUD tenant-scoped (Frente 2 / Bloco 2).

Escopo deste bloco: capacidades de **Pastor** (ACCESS_MATRIX §3.3 — listar todas,
ver detalhe, criar, editar). As ações destrutivas/LGPD (anonimizar, exportar) vêm
no Bloco 3; o acesso ESCOPADO de Líder/Coordenador (ver só a própria comunidade/
ministério) vem na Frente 3, junto com `Community` e o vínculo Person↔User que ele
exige (ACCESS_MATRIX §43) — por isso aqui tudo é `PastorRequiredMixin`.

Toda mutação passa pelo SERVICE (`apps.people.services`), nunca por `form.save()`:
é lá que vivem as barreiras de consentimento (OPS-05) e limite de plano (OPS-04).
A view só traduz o checkbox `consent_given` em `consent_given_at`.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, UpdateView

from apps.communities.models import Community
from apps.core.mixins import PastorRequiredMixin, TenantRequiredMixin
from apps.ministries.models import Ministry
from apps.people import services
from apps.people.forms import PersonForm
from apps.people.models import Person


class PersonListView(TenantRequiredMixin, PastorRequiredMixin, ListView):
    """Lista as pessoas ATIVAS da igreja, com filtros e busca. Apenas Pastor.

    Exclui anonimizadas (`anonymized_at` nulo). Filtros via querystring: `status`,
    `community`, `ministry`; busca `q` por nome. `select_related('community')`
    evita N+1 ao exibir a comunidade (P-ARQ-09).
    """

    model = Person
    template_name = 'people/person_list.html'
    context_object_name = 'persons'
    paginate_by = 25

    def get_queryset(self):
        qs = Person.objects.filter(anonymized_at__isnull=True).select_related(
            'community'
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


class PersonDetailView(TenantRequiredMixin, PastorRequiredMixin, DetailView):
    """Detalhe de uma pessoa. Apenas Pastor."""

    model = Person
    template_name = 'people/person_detail.html'
    context_object_name = 'person'


class PersonCreateView(TenantRequiredMixin, PastorRequiredMixin, FormView):
    """Cadastra uma pessoa via service (consent + limite de plano). Apenas Pastor."""

    template_name = 'people/person_form.html'
    form_class = PersonForm
    success_url = reverse_lazy('people:list')

    def form_valid(self, form):
        data = form.cleaned_data
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
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)
        messages.success(self.request, 'Pessoa cadastrada com sucesso.')
        return super().form_valid(form)


class PersonUpdateView(TenantRequiredMixin, PastorRequiredMixin, UpdateView):
    """Edita uma pessoa via service (revalida consent). Apenas Pastor."""

    model = Person
    form_class = PersonForm
    template_name = 'people/person_form.html'

    def get_success_url(self):
        return reverse_lazy('people:detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        data = form.cleaned_data
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
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)
        messages.success(self.request, 'Pessoa atualizada com sucesso.')
        # NÃO chamamos super().form_valid (faria form.save(), pulando o service).
        return redirect(self.get_success_url())
