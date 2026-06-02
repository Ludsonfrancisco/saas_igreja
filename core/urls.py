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
]

# django-debug-toolbar so existe em dev: o import fica DENTRO do guard de DEBUG
# para que prod (DEBUG=False, sem o app instalado) nunca tente importa-lo.
if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
