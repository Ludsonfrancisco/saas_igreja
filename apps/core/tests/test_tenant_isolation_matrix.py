"""Sprint 2 / Frente 7 — Gate de isolamento multi-tenant (SEC-01 / RISK-001).

Versão INICIAL do `test_tenant_isolation_matrix` (TEST_STRATEGY §6.1): percorre as
views autenticadas tenant-scoped JÁ EXISTENTES (Sprint 2 — usuários e convites) e
trava três contratos de isolamento:

1. barreira de login: anônimo é rediringido para o login do allauth;
2. barreira de schema: servida a partir do `public` (sem subdomínio de tenant) a
   view devolve 404 (`TenantRequiredMixin`) — não revela rotas de tenant nem
   redireciona;
3. ausência de vazamento: o Pastor da igreja A, com as duas igrejas povoadas, só
   enxerga dados da A — nunca da B.

À medida que novas views autenticadas nascem (Sprint 3+), elas DEVEM ser
acrescentadas a `AUTHENTICATED_TENANT_URLS` e ao corpo do teste de vazamento.

Requests rodam no host do tenant (`a.testserver`) ou do public (`localhost`).
`transaction=True` por causa do DDL de criar Church; search_path restaurado para
o public no teardown.
"""

import pytest
from django.db import connection
from django.test import Client
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.accounts.models import Invite, User
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'

# Views autenticadas tenant-scoped GET-áveis (Sprint 2 + Sprint 3 / OD-019).
AUTHENTICATED_TENANT_URLS = [
    '/configuracoes/usuarios/',
    '/configuracoes/convites/',
    '/configuracoes/convites/novo/',
    '/pessoas/',
    '/pessoas/nova/',
    '/comunidades/',
    '/ministerios/',
]


@pytest.fixture
def tenant_a_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


@pytest.fixture
def public_tenant(db):
    """Garante o tenant public + Domain `localhost` (idempotente)."""
    from apps.tenants.services import ensure_public_tenant

    ensure_public_tenant()
    connection.set_schema_to_public()
    yield
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _make_invite(church, email, invited_by):
    return Invite.objects.create(
        church=church,
        email=email,
        roles=['member'],
        invited_by=invited_by,
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('url', AUTHENTICATED_TENANT_URLS)
def test_authenticated_tenant_view_requires_login(tenant_a_client, church_a, url):
    """Anônimo em qualquer view tenant-scoped -> redirect para o login do allauth."""
    resp = tenant_a_client.get(url)
    assert resp.status_code == 302
    assert resp.url.startswith('/contas/login/')
    assert '/accounts/login/' not in resp.url


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('url', AUTHENTICATED_TENANT_URLS)
def test_authenticated_tenant_view_404_from_public_schema(public_tenant, url):
    """Servida do schema public (host `localhost`) -> 404 (TenantRequiredMixin).

    A barreira de schema roda ANTES da de login: mesmo anônimo, a rota
    tenant-scoped não existe no domínio público — 404 em vez de vazar a existência.
    """
    public_client = Client(HTTP_HOST='localhost')
    resp = public_client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_tenant_isolation_matrix(tenant_a_client, church_a, church_b):
    """Pastor de A só vê dados de A nas list-views existentes — nunca de B (RISK-001).

    Versão inicial do gate de isolamento (Sprint 2).
    """
    pastor_a = _make_user(church_a, 'pastor@a.com', ['pastor'])
    _make_user(church_a, 'membro@a.com', ['member'])
    _make_user(church_b, 'membro@b.com', ['member'])
    pastor_b = _make_user(church_b, 'pastor@b.com', ['pastor'])
    _make_invite(church_a, 'convidado@a.com', pastor_a)
    _make_invite(church_b, 'convidado@b.com', pastor_b)
    # Pessoas (model de TENANT): cada uma só existe no schema da sua igreja.
    with schema_context(church_a.schema_name):
        Person.objects.create(name='Pessoa A')
    with schema_context(church_b.schema_name):
        Person.objects.create(name='Pessoa B')

    tenant_a_client.force_login(pastor_a)

    # Usuários: só os da igreja A.
    resp = tenant_a_client.get('/configuracoes/usuarios/')
    assert resp.status_code == 200
    user_emails = {u.email for u in resp.context['users']}
    assert {'pastor@a.com', 'membro@a.com'} <= user_emails
    assert 'membro@b.com' not in user_emails
    assert 'pastor@b.com' not in user_emails

    # Convites: só os da igreja A.
    resp = tenant_a_client.get('/configuracoes/convites/')
    assert resp.status_code == 200
    invite_emails = {i.email for i in resp.context['invites']}
    assert 'convidado@a.com' in invite_emails
    assert 'convidado@b.com' not in invite_emails

    # Pessoas: o schema-per-tenant garante que A nunca veja a Pessoa B.
    resp = tenant_a_client.get('/pessoas/')
    assert resp.status_code == 200
    person_names = {p.name for p in resp.context['persons']}
    assert 'Pessoa A' in person_names
    assert 'Pessoa B' not in person_names
