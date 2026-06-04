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

from functools import cached_property

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView, TemplateView
from django_tenants.utils import get_public_schema_name

from apps.accounts import services
from apps.accounts.forms import (
    AcceptInviteForm,
    GrantSupportAccessForm,
    InviteForm,
    UserAccessForm,
)
from apps.accounts.models import Invite, SupportAccess, User
from apps.core.mixins import (
    PastorOrSecretaryMixin,
    PastorRequiredMixin,
    PlatformAdminRequiredMixin,
    TenantRequiredMixin,
)


class UserListView(TenantRequiredMixin, PastorOrSecretaryMixin, ListView):
    """Gestão de Acessos — lista os usuarios da igreja (RF-021 / OD-019).

    Pastor ou Secretário (OD-019). Tres camadas de permissao (P-ARQ-08):
    - view: TenantRequiredMixin (login + tenant) + PastorOrSecretaryMixin (papel);
    - queryset: filtra explicitamente por `church=request.tenant` (escopo por
      igreja — RISK-001, sem vazamento cross-tenant).

    Cada linha leva a `UserAccessView`, onde se concede funcoes (roles) e ativa/
    desativa, com as travas (RISK-015) aplicadas no service layer.
    """

    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        return User.objects.filter(church=self.request.tenant).order_by('email')


class UserAccessView(TenantRequiredMixin, PastorOrSecretaryMixin, FormView):
    """Concede funções (roles) e ativa/desativa um usuário da igreja (OD-019/RF-021).

    Pastor ou Secretário. As TRAVAS (RISK-015) — Secretário não mexe no papel
    `pastor` nem desativa Pastor; ninguém altera a própria conta; RN-004 — vivem em
    `change_roles`/`deactivate_user` (chamados com `actor=request.user`); aqui só
    surfaçamos o erro no form.

    O `target` é carregado SEMPRE filtrado por `church=request.tenant` (escopo por
    igreja — sem manipular usuário de outro tenant).
    """

    template_name = 'accounts/user_access_form.html'
    form_class = UserAccessForm
    success_url = reverse_lazy('accounts:user_list')

    @cached_property
    def target(self):
        return get_object_or_404(User, pk=self.kwargs['pk'], church=self.request.tenant)

    def get_initial(self):
        return {'roles': list(self.target.roles), 'is_active': self.target.is_active}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['target'] = self.target
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            if set(data['roles']) != set(self.target.roles):
                services.change_roles(
                    user=self.target,
                    new_roles=data['roles'],
                    actor=self.request.user,
                )
            if data['is_active'] and not self.target.is_active:
                services.reactivate_user(user=self.target, actor=self.request.user)
            elif not data['is_active'] and self.target.is_active:
                services.deactivate_user(user=self.target, actor=self.request.user)
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)
        messages.success(self.request, 'Acesso atualizado com sucesso.')
        return super().form_valid(form)


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


# --- Area de plataforma: SupportAccess (Frente 5 — RN-015 / RISK-009) -------
#
# Estas views vivem no schema PUBLIC (area de plataforma), NAO em tenant. Por
# isso usam `PlatformAdminRequiredMixin` (exige PlatformAdmin ativo + schema
# public), o espelho invertido do TenantRequiredMixin. As acoes sensiveis
# delegam ao service layer (`grant_support_access` / `revoke_support_access`),
# que audita no SecurityLog da igreja-alvo.


class SupportAccessListView(PlatformAdminRequiredMixin, ListView):
    """Lista os SupportAccess (area de plataforma). Apenas PlatformAdmin ativo.

    `select_related('admin', 'church', 'admin__user')` evita N+1 ao exibir o
    admin (e seu email), a igreja e o status de cada acesso (P-ARQ-09). O status
    (ativo/expirado/revogado) e derivado no template a partir de
    `ended_at`/`expires_at`.
    """

    model = SupportAccess
    template_name = 'accounts/support_access_list.html'
    context_object_name = 'support_accesses'

    def get_queryset(self):
        return SupportAccess.objects.select_related(
            'admin', 'church', 'admin__user'
        ).order_by('-started_at')


class SupportAccessGrantView(PlatformAdminRequiredMixin, FormView):
    """Concede SupportAccess a uma igreja. Apenas PlatformAdmin ativo (RN-015)."""

    template_name = 'accounts/support_access_form.html'
    form_class = GrantSupportAccessForm
    success_url = reverse_lazy('accounts:support_access_list')

    def form_valid(self, form):
        try:
            services.grant_support_access(
                admin=self.request.user.platform_admin,
                church=form.cleaned_data['church'],
                justification=form.cleaned_data['justification'],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return self.form_invalid(form)

        messages.success(self.request, 'Acesso de suporte concedido.')
        return super().form_valid(form)


class SupportAccessRevokeView(PlatformAdminRequiredMixin, View):
    """Revoga um SupportAccess. POST-only. Apenas PlatformAdmin ativo (RN-015)."""

    def post(self, request, pk):
        support_access = get_object_or_404(SupportAccess, pk=pk)
        services.revoke_support_access(support_access=support_access)
        messages.success(request, 'Acesso de suporte revogado.')
        return redirect('accounts:support_access_list')


# --- Conta do usuario: seguranca / MFA opt-in (Frente 6 — RF-018a) ----------
#
# Ponto de entrada pt-BR na conta para o MFA. O fluxo real (ativar TOTP com QR,
# ver/regerar recovery codes, desativar) usa as views NATIVAS do allauth.mfa
# (`mfa_index` e filhas, sob /contas/2fa/) — aqui so expomos o status e o CTA.


class AccountSecurityView(LoginRequiredMixin, TemplateView):
    """Pagina 'Seguranca da conta': status do MFA + atalho para a gerencia.

    Disponivel a QUALQUER usuario autenticado (MFA e opt-in nesta sprint),
    inclusive PlatformAdmin no schema public — por isso `LoginRequiredMixin` e
    NAO `TenantRequiredMixin`. O enforcement obrigatorio (pastor/PlatformAdmin) e
    Sprint 7.
    """

    template_name = 'accounts/account_security.html'

    def get_context_data(self, **kwargs):
        from allauth.mfa.models import Authenticator
        from allauth.mfa.utils import is_mfa_enabled

        context = super().get_context_data(**kwargs)
        context['mfa_enabled'] = is_mfa_enabled(
            self.request.user, [Authenticator.Type.TOTP]
        )
        return context
