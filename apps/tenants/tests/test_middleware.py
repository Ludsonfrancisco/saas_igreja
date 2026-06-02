"""Sprint 1 — resolucao de tenant por subdominio (TENANT-05 / SEC-01).

Cobre o teste minimo `test_tenant_middleware_resolves_by_subdomain` (SPRINTS
Sprint 1): um request com Host do tenant A deve fazer o middleware definir o
search_path do Postgres para o schema do tenant e anexar `request.tenant`.
"""

import pytest
from django.db import connection
from django.test import RequestFactory
from django_tenants.utils import get_public_schema_name

from apps.tenants.middleware import TenantMiddleware


@pytest.mark.django_db(transaction=True)
def test_tenant_middleware_resolves_by_subdomain(church_a):
    middleware = TenantMiddleware(get_response=lambda request: None)
    request = RequestFactory().get('/', HTTP_HOST='a.testserver')

    middleware.process_request(request)

    try:
        assert connection.schema_name == 'tenant_a'
        assert request.tenant.schema_name == 'tenant_a'
    finally:
        # Restaura o search_path para public para nao contaminar outros testes.
        connection.set_schema_to_public()
        assert connection.schema_name == get_public_schema_name()
