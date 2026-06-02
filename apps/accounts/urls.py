"""URLs da app accounts (namespace 'accounts').

Incluidas pelo ROOT_URLCONF sob o prefixo `configuracoes/`. Estas rotas sao
tenant-scoped: so respondem em contexto de tenant (as views aplicam
TenantRequiredMixin).
"""

from django.urls import path

from apps.accounts.views import UserListView

app_name = 'accounts'

urlpatterns = [
    path('usuarios/', UserListView.as_view(), name='user_list'),
]
