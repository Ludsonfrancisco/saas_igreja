"""Admin do projeto — base de segurança multi-tenant (SEC-01 / TENANT-05).

O Django admin padrão NÃO é tenant-aware: ele não passa pela barreira do
`TenantRequiredMixin` nem garante o isolamento por schema, então expor seus CRUDs
em produção arrisca vazamento cross-tenant (RISK-001). Este módulo concentra o
`TenantAdminMixin`, base obrigatória de TODO `ModelAdmin` do projeto, que desliga
o admin em produção.

Estado atual (Sprint 2): nenhum modelo é registrado no admin ainda — o mixin
existe como infraestrutura para os `ModelAdmin` das próximas sprints herdarem.
As URLs do admin também não são montadas no ROOT_URLCONF (ver `core/urls.py`),
de modo que o admin padrão já não é roteável; o mixin é a segunda linha, caso
algum `ModelAdmin` seja registrado e o site venha a ser montado.
"""

from django.conf import settings


class TenantAdminMixin:
    """ModelAdmin base que PROÍBE o Django admin padrão em produção.

    Em produção (`DEBUG=False`) todas as permissões do admin retornam `False` — o
    modelo desaparece do site e nenhum CRUD é acessível. Em desenvolvimento
    (`DEBUG=True`) o comportamento padrão do `ModelAdmin` é preservado para
    inspeção local.

    Aplica-se a TODOS os `ModelAdmin` (TECH_SPEC §estrutura / TENANT-05). O curto-
    circuito `_admin_allowed() and super()...` garante que, em prod, a checagem
    nem sequer delega ao `super()` — o admin fica inerte.
    """

    def _admin_allowed(self) -> bool:
        # Habilitado SOMENTE fora de produção. DEBUG=False (prod e o test runner)
        # => admin desligado.
        return settings.DEBUG

    def has_module_permission(self, request):
        return self._admin_allowed() and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return self._admin_allowed() and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return self._admin_allowed() and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._admin_allowed() and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._admin_allowed() and super().has_delete_permission(request, obj)
