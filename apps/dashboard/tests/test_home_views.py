"""Sprint 6.6 / Bloco 2+3 — Home nova: escopo por papel, isolamento, render real.

Cobertura (RF-102/103/104 + RISK-001):
- `test_home_upcoming_gatherings_scope`: próximas programações da igreja A nunca
  trazem encontros da B (gate de isolamento cross-tenant);
- GAP escopado: Pastor vê todos os ministérios; Coordenador só os que coordena;
- home aberta a qualquer papel logado (Membro: 200, GAP vazio); anônimo => redirect;
- Bloco 3: a home (`/`) e os fragmentos HTMX do calendário (troca de mês, encontros
  do dia) renderizam os templates REAIS sem erro; data inválida => 404.

Os testes de ESCOPO usam stub de template (locmem) e assertam sobre `resp.context`.
Os de RENDER usam os templates reais (pegam erro de sintaxe/url/widthratio). Host
`a.testserver`; criar Church (DDL) => `transaction=True`.
"""

import pytest
from django.db import connection
from django.test import Client, override_settings
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.gatherings.models import Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
HOME_URL = '/'
CALENDAR_URL = '/inicio/calendario/'

stub_templates = override_settings(
    TEMPLATES=[
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': False,
            'OPTIONS': {
                'loaders': [
                    (
                        'django.template.loaders.locmem.Loader',
                        {'dashboard/home.html': 'ok'},
                    ),
                ],
                'context_processors': [
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        }
    ]
)


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _future_worship(title):
    return Gathering.objects.create(
        gathering_type=Gathering.Type.WORSHIP,
        title=title,
        date=timezone.localdate() + timezone.timedelta(days=3),
    )


# --------------------------------------------------------------------------- #
# Gate de isolamento — próximas programações não vazam entre tenants
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
def test_home_upcoming_gatherings_scope(tenant_client, church_a, church_b):
    """Pastor de A só vê os encontros futuros da A — nunca os da B (RISK-001)."""
    pastor_a = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        _future_worship('Culto A')
    with schema_context(church_b.schema_name):
        _future_worship('Culto B')

    tenant_client.force_login(pastor_a)
    resp = tenant_client.get(HOME_URL)
    assert resp.status_code == 200
    titles = {g.title for g in resp.context['upcoming_gatherings']}
    assert 'Culto A' in titles
    assert 'Culto B' not in titles


# --------------------------------------------------------------------------- #
# GAP escopado por papel
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
def test_home_gap_pastor_sees_all_ministries(tenant_client, church_a):
    """Pastor vê o GAP de todos os ministérios ativos."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        Ministry.objects.create(name='Louvor', volunteers_needed=2)
        Ministry.objects.create(name='Diaconia', volunteers_needed=1)

    tenant_client.force_login(pastor)
    resp = tenant_client.get(HOME_URL)
    names = {g['name'] for g in resp.context['health']['items']}
    assert names == {'Louvor', 'Diaconia'}


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_home_gap_coordinator_sees_only_own(tenant_client, church_a):
    """Coordenador (`leader`) só vê o GAP do(s) ministério(s) que coordena."""
    coordinator = _user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='Coord', user_id=coordinator.id)
        mine = Ministry.objects.create(name='Meu', volunteers_needed=3)
        mine.coordinators.add(person)
        Ministry.objects.create(name='Alheio', volunteers_needed=3)

    tenant_client.force_login(coordinator)
    resp = tenant_client.get(HOME_URL)
    names = {g['name'] for g in resp.context['health']['items']}
    assert names == {'Meu'}


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_home_member_access_but_empty_gap(tenant_client, church_a):
    """Membro acessa a home (RF-102/103 "Todos"), mas o GAP é vazio (coordena nada)."""
    member = _user(church_a, 'member@a.com', ['member'])
    with schema_context(church_a.schema_name):
        Ministry.objects.create(name='Louvor', volunteers_needed=2)

    tenant_client.force_login(member)
    resp = tenant_client.get(HOME_URL)
    assert resp.status_code == 200
    assert resp.context['health']['items'] == []


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_home_anonymous_redirected_to_login(tenant_client, church_a):
    """Sem login => redirect (LoginRequiredMixin via TenantRequiredMixin)."""
    resp = tenant_client.get(HOME_URL)
    assert resp.status_code == 302


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_calendar_fragment_requires_login(tenant_client, church_a):
    """Fragmento do calendário também exige login (mesmo gate da home)."""
    resp = tenant_client.get(CALENDAR_URL)
    assert resp.status_code == 302


# --------------------------------------------------------------------------- #
# Render dos templates REAIS (Bloco 3) — pegam erro de sintaxe/url/widthratio
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_home_page_renders_real_template(tenant_client, church_a):
    """A home `/` (Painel Oikonos) renderiza com Saúde do Ministério + KPIs (real)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        Ministry.objects.create(name='Louvor', volunteers_needed=4)
        Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP,
            title='Culto de Domingo',
            date=timezone.localdate() + timezone.timedelta(days=2),
        )

    tenant_client.force_login(pastor)
    resp = tenant_client.get(HOME_URL)
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'Painel Oikonos' in body
    assert 'Saúde do Ministério' in body
    assert 'Próximas programações' in body
    assert 'Pessoas ativas' in body  # KPI real renderizado
    assert 'Em breve' in body  # placeholder das seções sem backend


@pytest.mark.django_db(transaction=True)
def test_calendar_fragment_month_nav_renders(tenant_client, church_a):
    """Troca de mês via HTMX: o fragmento renderiza o mês pedido (rótulo pt-BR)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)
    resp = tenant_client.get(CALENDAR_URL, {'year': 2026, 'month': 7})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'Julho 2026' in body
    assert 'hx-get' in body  # botões de navegação de mês


@pytest.mark.django_db(transaction=True)
def test_day_fragment_lists_gatherings(tenant_client, church_a):
    """Clique no dia: o fragmento lista os encontros daquela data (template real)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP,
            title='Culto no Dia',
            date=timezone.localdate(),
        )
    day_iso = timezone.localdate().isoformat()

    tenant_client.force_login(pastor)
    resp = tenant_client.get(f'/inicio/dia/{day_iso}/')
    assert resp.status_code == 200
    assert 'Culto no Dia' in resp.content.decode()


@pytest.mark.django_db(transaction=True)
def test_day_fragment_invalid_date_404(tenant_client, church_a):
    """Data ISO inválida no fragmento do dia => 404 (não vaza)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)
    resp = tenant_client.get('/inicio/dia/2026-13-99/')
    assert resp.status_code == 404
