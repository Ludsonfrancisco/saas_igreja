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

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.accounts.models import Invite, User
from apps.files import services as files_services
from apps.finance.models import Category, Transaction
from apps.gatherings.models import Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person
from apps.schedules.models import Schedule

GOOD_PASSWORD = 'Senha@123'
PDF_BYTES = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< >>\nendobj\n'

# Views autenticadas tenant-scoped GET-áveis (Sprint 2..6). `/painel/` é Pastor-only,
# mas as duas baterias abaixo testam anônimo (→ login) e schema public (→ 404), que
# valem para qualquer gate de papel.
AUTHENTICATED_TENANT_URLS = [
    # Home "Painel Oikonos" (Sprint 6.6) na raiz + fragmentos HTMX do calendário.
    '/',
    '/inicio/calendario/',
    '/inicio/dia/2026-06-01/',
    '/configuracoes/usuarios/',
    '/configuracoes/convites/',
    '/configuracoes/convites/novo/',
    '/pessoas/',
    '/pessoas/nova/',
    '/comunidades/',
    # Comunidades v2 (RF-108): lançamento de presença da célula (rota dinâmica; ids
    # arbitrários servem para as baterias anônimo→login e public→404).
    '/comunidades/1/lancamento/1/',
    '/ministerios/',
    '/encontros/',
    '/encontros/novo/',
    # Escalas v2 (RF-111/112): tela por evento + modal (rota dinâmica; id arbitrário
    # serve às baterias anônimo→login e public→404).
    '/escalas/eventos/',
    '/escalas/eventos/1/escalar/',
    '/escalas/',
    '/escalas/nova/',
    '/escalas/excecao/nova/',
    '/arquivos/',
    '/painel/',
    '/painel/comunidade/',
    '/painel/ministerio/',
    # Financeiro (Sprint 6.7) — Pastor/Tesoureiro; as baterias abaixo testam anônimo
    # (→ login) e schema public (→ 404), válidas para qualquer gate de papel.
    '/financeiro/',
    '/financeiro/lancamentos/',
    '/financeiro/lancamentos/novo/',
    '/financeiro/categorias/',
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
        gathering_a = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP,
            title='Culto A',
            date=timezone.now().date(),
        )
        # Escala (Sprint 5): voluntário escalado num ministério da igreja A.
        ministry_a = Ministry.objects.create(name='Louvor A')
        volunteer_a = Person.objects.create(name='Voluntario A')
        volunteer_a.ministries.add(ministry_a)
        Schedule.objects.create(
            ministry=ministry_a, person=volunteer_a, gathering=gathering_a
        )
        # Financeiro (Sprint 6.7): lançamento da igreja A.
        cat_a = Category.objects.create(name='Dizimo A', kind=Category.Kind.INCOME)
        Transaction.objects.create(
            category=cat_a, date=timezone.now().date(), amount=Decimal('100.00')
        )
    with schema_context(church_b.schema_name):
        Person.objects.create(name='Pessoa B')
        gathering_b = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP,
            title='Culto B',
            date=timezone.now().date(),
        )
        ministry_b = Ministry.objects.create(name='Louvor B')
        volunteer_b = Person.objects.create(name='Voluntario B')
        volunteer_b.ministries.add(ministry_b)
        Schedule.objects.create(
            ministry=ministry_b, person=volunteer_b, gathering=gathering_b
        )
        cat_b = Category.objects.create(name='Dizimo B', kind=Category.Kind.INCOME)
        Transaction.objects.create(
            category=cat_b, date=timezone.now().date(), amount=Decimal('999.00')
        )

    # Arquivos (Sprint 6): um FileAsset em cada schema; o storage isola por tenant.
    with schema_context(church_a.schema_name):
        files_services.upload_file(
            uploaded_file=SimpleUploadedFile('ata-a.pdf', PDF_BYTES, 'application/pdf'),
            uploaded_by_id=pastor_a.id,
        )
    with schema_context(church_b.schema_name):
        files_services.upload_file(
            uploaded_file=SimpleUploadedFile('ata-b.pdf', PDF_BYTES, 'application/pdf'),
            uploaded_by_id=pastor_b.id,
        )

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

    # Encontros: idem — A só enxerga o culto da própria igreja (Sprint 4).
    resp = tenant_a_client.get('/encontros/')
    assert resp.status_code == 200
    gathering_titles = {g.title for g in resp.context['gatherings']}
    assert 'Culto A' in gathering_titles
    assert 'Culto B' not in gathering_titles

    # Escalas: idem — A só enxerga a escala do próprio ministério (Sprint 5).
    resp = tenant_a_client.get('/escalas/')
    assert resp.status_code == 200
    schedule_ministries = {s.ministry.name for s in resp.context['schedules']}
    assert 'Louvor A' in schedule_ministries
    assert 'Louvor B' not in schedule_ministries

    # Escalas v2: a tela por evento (RF-111) só lista os encontros da própria igreja.
    resp = tenant_a_client.get('/escalas/eventos/')
    assert resp.status_code == 200
    event_titles = {item['gathering'].title for item in resp.context['events']}
    assert 'Culto A' in event_titles
    assert 'Culto B' not in event_titles

    # Arquivos: o Pastor de A só enxerga o arquivo da própria igreja (Sprint 6).
    resp = tenant_a_client.get('/arquivos/')
    assert resp.status_code == 200
    file_names = {f.filename for f in resp.context['file_assets']}
    assert 'ata-a.pdf' in file_names
    assert 'ata-b.pdf' not in file_names

    # Financeiro: A só enxerga os lançamentos da própria igreja (Sprint 6.7).
    resp = tenant_a_client.get('/financeiro/lancamentos/')
    assert resp.status_code == 200
    txn_categories = {t.category.name for t in resp.context['transactions']}
    assert 'Dizimo A' in txn_categories
    assert 'Dizimo B' not in txn_categories
