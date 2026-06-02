"""Root URLconf.

Observabilidade (`/health/`, `/ready/`) ja registrada aqui (TECH_SPEC §12.1):
vive no ROOT_URLCONF e e alcancada sem subdominio de tenant, pois o
`TenantMiddleware` faz bypass desses caminhos. Landing e rotas das apps
entram em blocos posteriores da Sprint 1.
"""

from django.conf import settings
from django.urls import include, path

from apps.core.views import health, ready

urlpatterns: list[path] = [
    path('health/', health, name='health'),
    path('ready/', ready, name='ready'),
    # Fluxos de autenticacao do allauth (login, logout, reset/confirm de senha)
    # sob prefixo pt-BR. O cadastro publico esta fechado (AccountAdapter), mas a
    # rota de signup ainda e incluida pelo allauth — ela responde fechada.
    path('contas/', include('allauth.urls')),
    # Configuracoes tenant-scoped (Frente 3): listagem de usuarios da igreja.
    # As views aplicam TenantRequiredMixin, entao so respondem em contexto de
    # tenant (no public, o mixin devolve 404).
    path('configuracoes/', include('apps.accounts.urls')),
]

# django-debug-toolbar so existe em dev: o import fica DENTRO do guard de DEBUG
# para que prod (DEBUG=False, sem o app instalado) nunca tente importa-lo.
if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
