"""Infra de testes E2E (Sprint 6.5 / Bloco 6) — Playwright + Django live_server.

Desafio django-tenants: o tenant é resolvido pelo Host. O `live_server` sobe num
host:porta; aqui criamos um `Domain` casado com o HOST real do live_server (ex.:
`localhost`) apontando para um tenant E2E, e populamos o schema do tenant. Assim o
browser navegando para `live_server.url` cai no schema certo.

Marcar os testes com `@pytest.mark.django_db(transaction=True)` (o `live_server`
exige banco transacional; a criação de Church dispara DDL com COMMIT).
"""

import os
from urllib.parse import urlparse

# Playwright (sync API) roda um event loop na thread de teste; o guard de
# async-safety do Django barraria nossas chamadas ORM (síncronas de fato) nas
# fixtures/asserções. Liberamos SÓ no escopo E2E (só dispara em contexto async,
# que apenas o E2E cria — não afeta os testes sync normais). Antes de importar ORM.
os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', '1')

import pytest  # noqa: E402
from django.db import connection  # noqa: E402

E2E_SCHEMA = 'tenant_e2e'
E2E_PASSWORD = 'Senha@123'


def _drop_schema(name):
    with connection.cursor() as cur:
        cur.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')


@pytest.fixture
def e2e(live_server, transactional_db):
    """Tenant E2E + Domain casado ao host do live_server. Retorna (church, live_server).

    Cria também um Pastor (login completo) e expõe helpers de dados via
    `schema_context`. Teardown derruba o schema e o Domain.
    """
    from apps.accounts.models import User
    from apps.tenants.models import Church, Domain

    host = urlparse(live_server.url).hostname  # 'localhost' ou '127.0.0.1'

    church = Church.objects.create(
        name='Igreja E2E',
        slug='e2e',
        schema_name=E2E_SCHEMA,
        accent_color='#123456',
    )
    Domain.objects.create(domain=host, tenant=church, is_primary=True)

    pastor = User.objects.create_user(
        email='pastor@e2e.com',
        password=E2E_PASSWORD,
        roles=['pastor'],
        church=church,
    )

    yield {'church': church, 'live_server': live_server, 'host': host, 'pastor': pastor}

    _drop_schema(E2E_SCHEMA)
    Domain.objects.filter(tenant=church).delete()
    User.objects.filter(church=church).delete()
    church.delete()
    connection.set_schema_to_public()


def login(page, live_server, email, password=E2E_PASSWORD):
    """Faz login via formulário allauth e espera o redirect pós-login."""
    page.goto(f'{live_server.url}/contas/login/')
    page.fill('input[name="login"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
