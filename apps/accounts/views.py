"""Views da app accounts (Sprint 2 / Frente 3 — autorizacao multi-role).

Por ora, a listagem de usuarios da igreja (configuracoes). Toda view e
tenant-scoped (TenantRequiredMixin) e restrita por papel na camada de view
(PastorRequiredMixin) — RN-003a / P-ARQ-08 / TENANT-05. O styling Athos fica
para a frente de frontend; o template aqui e markup minimo pt-BR.
"""

from django.views.generic import ListView

from apps.accounts.models import User
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
