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
    # App accounts: UM unico include na raiz, com namespace unico 'accounts'.
    # O proprio urlconf da app carrega os prefixos (`configuracoes/...` para as
    # rotas tenant-scoped; `contas/convite/<token>/` para o aceite PUBLICO de
    # convite). Montar um SO include preserva o reverse de todas as rotas do
    # namespace (incluir o mesmo namespace em dois includes quebraria o reverse).
    # Precede o allauth para que `contas/convite/<token>/` nao colida com as
    # rotas do allauth sob o mesmo prefixo `contas/`.
    path('', include('apps.accounts.urls')),
    # App people: CRUD de Pessoas sob `pessoas/` (namespace 'people'), tenant-scoped.
    path('', include('apps.people.urls')),
    # App communities: CRUD de Comunidades sob `comunidades/` (namespace 'communities').
    path('', include('apps.communities.urls')),
    # App ministries: CRUD de Ministérios sob `ministerios/` (namespace 'ministries').
    path('', include('apps.ministries.urls')),
    # App gatherings: CRUD de Encontros sob `encontros/` (namespace 'gatherings').
    path('', include('apps.gatherings.urls')),
    # App schedules: CRUD de Escalas sob `escalas/` (namespace 'schedules').
    path('', include('apps.schedules.urls')),
    # Fluxos de autenticacao do allauth (login, logout, reset/confirm de senha)
    # sob prefixo pt-BR. O cadastro publico esta fechado (AccountAdapter), mas a
    # rota de signup ainda e incluida pelo allauth — ela responde fechada.
    path('contas/', include('allauth.urls')),
]

# django-debug-toolbar so existe em dev: o import fica DENTRO do guard de DEBUG
# para que prod (DEBUG=False, sem o app instalado) nunca tente importa-lo.
if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
