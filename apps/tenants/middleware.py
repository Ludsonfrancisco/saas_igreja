"""Resolucao de tenant por subdominio (TECH_SPEC §4.3 / TENANT-05 / SEC-01).

`TenantMiddleware` e uma subclasse fina de `TenantMainMiddleware` do
django-tenants, que executa exatamente os passos de §4.3 por request:

1. Le o `Host` (ex.: `<slug>.saasigreja.com`, ou `<slug>.localhost` em dev).
2. Consulta `public.tenants_domain` para achar a `Church` correspondente.
3. Define o `search_path` do PostgreSQL para `tenant_<slug>, public`.
4. Coloca `request.tenant = Church(...)` para uso nas views.

Nao reimplementamos nada disso (STYLE-03): apenas endurecemos o comportamento
para host desconhecido e fazemos bypass dos endpoints de observabilidade.

Bypass de observabilidade (TECH_SPEC §12.1): `process_request` retorna cedo
para `/health/` e `/ready/`, sem executar a resolucao de tenant. Motivo:
`/health/` (liveness) nao pode depender do banco — se o lookup de `Domain`
rodasse, um Postgres fora do ar derrubaria a sonda; e a sonda deve responder
mesmo para um `Host` desconhecido (ex.: o monitor externo), que de outra
forma cairia no `no_tenant_found` -> 404. `/ready/` faz suas proprias
verificacoes de Postgres e Redis dentro da view. Ao retornar cedo, o
django-tenants nao consulta `Domain` nem define `request.tenant`, e o Django
cai no ROOT_URLCONF (`core.urls`), onde as rotas health/ready vivem.
"""

from django.http import Http404
from django_tenants.middleware.main import TenantMainMiddleware


class TenantMiddleware(TenantMainMiddleware):
    """Middleware de resolucao de tenant do SaaS Igreja.

    Endurece o tratamento de host desconhecido: em vez de qualquer fallback
    silencioso para o schema `public`, devolve HTTP 404. Isso evita vazar a
    existencia de rotas/tenant para um subdominio inexistente (SEC-01) e e
    a opcao mais conservadora em seguranca: nunca servir conteudo de tenant
    a partir de um host nao resolvido.
    """

    HEALTH_PATHS = ('/health/', '/ready/')

    def process_request(self, request):
        if request.path in self.HEALTH_PATHS:
            # observabilidade vive fora do roteamento de tenant; nao resolve
            # Domain (liveness nao pode depender do banco).
            return
        return super().process_request(request)

    def no_tenant_found(self, request, hostname):
        raise Http404(f'Tenant nao encontrado para o host "{hostname}".')
