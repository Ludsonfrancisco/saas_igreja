"""URLs da app accounts (namespace unico 'accounts').

Este urlconf e montado UMA UNICA VEZ no ROOT_URLCONF, na raiz (`''`), e cada
pattern carrega seu proprio prefixo. Mantemos um SO `app_name='accounts'` (e,
portanto, um so namespace) para que `reverse('accounts:...')` resolva TODAS as
rotas — incluir o mesmo namespace em dois `include()` separados quebraria o
reverse das rotas do segundo include (Django registra duas instancias, mas o
namespace aponta so para a primeira).

Dois grupos de rotas convivem aqui:
- tenant-scoped, sob `configuracoes/`: usuarios e gestao de convites. As views
  aplicam TenantRequiredMixin (so respondem em contexto de tenant; no public,
  404).
- PUBLICA, sob `contas/convite/<token>/`: o aceite de convite. O convidado ainda
  nao tem conta, entao a view NAO usa TenantRequiredMixin/LoginRequired; a
  barreira de tenant e feita na propria view (404 no public + `expected_church`
  no service). `<uuid:token>` casa o tipo de Invite.token (UUIDField). Esta rota
  precisa vir ANTES do include do allauth em core/urls.py (ambas sob `contas/`).
"""

from django.urls import path

from apps.accounts.views import (
    InviteAcceptView,
    InviteCancelView,
    InviteCreateView,
    InviteListView,
    InviteResendView,
    UserListView,
)

app_name = 'accounts'

urlpatterns = [
    # Tenant-scoped (prefixo `configuracoes/`).
    path('configuracoes/usuarios/', UserListView.as_view(), name='user_list'),
    path('configuracoes/convites/', InviteListView.as_view(), name='invite_list'),
    path(
        'configuracoes/convites/novo/',
        InviteCreateView.as_view(),
        name='invite_create',
    ),
    path(
        'configuracoes/convites/<int:pk>/reenviar/',
        InviteResendView.as_view(),
        name='invite_resend',
    ),
    path(
        'configuracoes/convites/<int:pk>/cancelar/',
        InviteCancelView.as_view(),
        name='invite_cancel',
    ),
    # Publica (prefixo `contas/`): aceite de convite.
    path(
        'contas/convite/<uuid:token>/',
        InviteAcceptView.as_view(),
        name='invite_accept',
    ),
]
