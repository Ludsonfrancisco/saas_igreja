"""Views da app accounts (Sprint 2 / Frentes 3 e 4).

Frente 3: listagem de usuarios da igreja. Frente 4: ciclo de vida de convites
(criar, listar, reenviar, cancelar, aceitar).

Toda view AUTENTICADA e tenant-scoped (TenantRequiredMixin) e restrita por papel
(PastorRequiredMixin) — RN-003a / P-ARQ-08 / TENANT-05. A UNICA excecao e
`InviteAcceptView`: e PUBLICA por natureza (o convidado ainda nao tem conta),
mas continua amarrada ao tenant via `request.tenant` (resolvido pelo
TenantMiddleware antes da auth) e via `expected_church` no service.

O styling Athos fica para a frente de frontend; os templates aqui sao markup
minimo pt-BR.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView
from django_tenants.utils import get_public_schema_name

from apps.accounts import services
from apps.accounts.forms import AcceptInviteForm, InviteForm
from apps.accounts.models import Invite, User
from apps.core.mixins import PastorRequiredMixin, TenantRequiredMixin


class UserListView(TenantRequiredMixin, PastorRequiredMixin, ListView):
    """Lista os usuarios da igreja atual. Apenas Pastor (RN-003a / RF-021).

    Tres camadas de permissao (P-ARQ-08):
    - view: TenantRequiredMixin (login + tenant) + PastorRequiredMixin (papel);
    - queryset: filtra explicitamente por `church=request.tenant` (escopo por
      igreja — RISK-001, sem vazamento cross-tenant);
    - User e model publico, mas o filtro de church garante o recorte do tenant.

    `church` ja esta carregado via FK simples; nao ha relacao iterada no template
    que dispare N+1 (P-ARQ-09).
    """

    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        return User.objects.filter(church=self.request.tenant).order_by('email')


class InviteListView(TenantRequiredMixin, PastorRequiredMixin, ListView):
    """Lista os convites PENDENTES da igreja atual. Apenas Pastor (RN-003a).

    Pendentes = `accepted_at__isnull=True`. `select_related('invited_by')` evita
    N+1 ao exibir quem convidou (P-ARQ-09). Escopo por `church=request.tenant`
    (sem vazamento cross-tenant).
    """

    model = Invite
    template_name = 'accounts/invite_list.html'
    context_object_name = 'invites'

    def get_queryset(self):
        return (
            Invite.objects.filter(church=self.request.tenant, accepted_at__isnull=True)
            .select_related('invited_by')
            .order_by('email')
        )


class InviteCreateView(TenantRequiredMixin, PastorRequiredMixin, FormView):
    """Cria um convite e dispara o email de aceite. Apenas Pastor (RN-003a)."""

    template_name = 'accounts/invite_form.html'
    form_class = InviteForm
    success_url = reverse_lazy('accounts:invite_list')

    def form_valid(self, form):
        try:
            services.create_invite(
                church=self.request.tenant,
                email=form.cleaned_data['email'],
                roles=form.cleaned_data['roles'],
                invited_by=self.request.user,
                build_accept_url=lambda token: self.request.build_absolute_uri(
                    reverse('accounts:invite_accept', kwargs={'token': token})
                ),
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)

        messages.success(self.request, 'Convite enviado com sucesso.')
        return super().form_valid(form)


class InviteResendView(TenantRequiredMixin, PastorRequiredMixin, View):
    """Reenvia um convite pendente (regenera token). POST-only. Apenas Pastor."""

    def post(self, request, pk):
        invite = get_object_or_404(Invite, pk=pk, church=request.tenant)
        try:
            services.resend_invite(
                invite=invite,
                actor=request.user,
                build_accept_url=lambda token: request.build_absolute_uri(
                    reverse('accounts:invite_accept', kwargs={'token': token})
                ),
            )
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, 'Convite reenviado com sucesso.')
        return redirect('accounts:invite_list')


class InviteCancelView(TenantRequiredMixin, PastorRequiredMixin, View):
    """Cancela (hard delete) um convite pendente. POST-only. Apenas Pastor."""

    def post(self, request, pk):
        invite = get_object_or_404(Invite, pk=pk, church=request.tenant)
        services.cancel_invite(invite=invite, actor=request.user)
        messages.success(request, 'Convite cancelado.')
        return redirect('accounts:invite_list')


class InviteAcceptView(View):
    """Aceite PUBLICO de convite: cria a conta a partir do token (RN-003a).

    NAO usa TenantRequiredMixin nem LoginRequired: o convidado ainda nao tem
    conta. A barreira de tenant e mantida de duas formas:
    - se o request esta no schema public (sem tenant), devolve 404;
    - o aceite passa `expected_church=request.tenant` ao service, que recusa
      tokens de outra igreja (defesa cross-tenant — RISK-001).

    GET: valida o token e mostra o form de senha, ou a pagina de erro pt-BR.
    POST: valida senha (validate_password) e confirmacao, chama o service e
    redireciona ao login.
    """

    def _require_tenant(self):
        if connection.schema_name == get_public_schema_name():
            raise Http404()

    def _load_valid_invite(self, request, token):
        """Retorna o Invite valido para `token`/tenant, ou None se invalido."""
        from django.utils import timezone

        try:
            invite = Invite.objects.select_related('church').get(token=token)
        except Invite.DoesNotExist:
            return None
        if invite.church_id != request.tenant.id:
            return None
        if invite.accepted_at is not None:
            return None
        if invite.expires_at < timezone.now():
            return None
        return invite

    def get(self, request, token):
        self._require_tenant()
        invite = self._load_valid_invite(request, token)
        if invite is None:
            return render(request, 'accounts/invite_invalid.html', status=404)
        return render(
            request,
            'accounts/invite_accept.html',
            {'form': AcceptInviteForm(), 'invite': invite},
        )

    def post(self, request, token):
        self._require_tenant()
        invite = self._load_valid_invite(request, token)
        if invite is None:
            return render(request, 'accounts/invite_invalid.html', status=404)

        form = AcceptInviteForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                'accounts/invite_accept.html',
                {'form': form, 'invite': invite},
            )

        try:
            services.accept_invite(
                token=token,
                password=form.cleaned_data['password1'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                expected_church=request.tenant,
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return render(
                request,
                'accounts/invite_accept.html',
                {'form': form, 'invite': invite},
            )

        messages.success(request, 'Conta criada com sucesso. Faca login.')
        return redirect('account_login')
