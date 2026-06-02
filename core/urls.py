"""Root URLconf.

Observabilidade (`/health/`, `/ready/`) ja registrada aqui (TECH_SPEC §12.1):
vive no ROOT_URLCONF e e alcancada sem subdominio de tenant, pois o
`TenantMiddleware` faz bypass desses caminhos. Landing e rotas das apps
entram em blocos posteriores da Sprint 1.
"""

from django.urls import path

from apps.core.views import health, ready

urlpatterns: list[path] = [
    path('health/', health, name='health'),
    path('ready/', ready, name='ready'),
]
