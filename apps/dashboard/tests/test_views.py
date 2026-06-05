"""Sprint 6 / Bloco 5 — views do dashboard: escopo, gate de papel, sem vazamento.

Cobertura (ACCESS_MATRIX §3.9 + RISK-001):
- caminho feliz das 3 views (200 + `metrics` no contexto com numeros corretos);
- Lider ve so a(s) sua(s) comunidade(s); Coordenador so o(s) seu(s) ministerio(s);
- gate de papel: Lider/Membro NAO acessam o dashboard completo (403); Membro nao
  acessa os simplificados;
- sem vazamento: metrica escopada de A nao inclui dados de outra comunidade/
  ministerio nem de outro tenant.

Templates HTML sao do frontend (fora do escopo do backend): stub via locmem loader;
assertamos sobre `resp.context['metrics']` (a logica de backend), nao sobre o HTML.
Host `a.testserver`/`b.testserver` nos requests; DDL de criar Church exige
`@pytest.mark.django_db(transaction=True)`.
"""

import pytest
from django.db import connection
from django.test import Client, override_settings
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.gatherings.models import Attendance, Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'

PASTOR_URL = '/painel/'
LEADER_URL = '/painel/comunidade/'
COORDINATOR_URL = '/painel/ministerio/'

_STUB_TEMPLATES = {
    'dashboard/dashboard_pastor.html': 'ok',
    'dashboard/dashboard_leader.html': 'ok',
    'dashboard/dashboard_coordinator.html': 'ok',
}

stub_templates = override_settings(
    TEMPLATES=[
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': False,
            'OPTIONS': {
                'loaders': [
                    ('django.template.loaders.locmem.Loader', _STUB_TEMPLATES),
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


def _present(person, gathering):
    return Attendance.objects.create(
        person=person, gathering=gathering, is_present=True
    )


# --------------------------------------------------------------------------- #
# Caminho feliz — Pastor (completo)
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
def test_pastor_dashboard_happy_path(tenant_client, church_a):
    """Pastor: 200 + metrics completas da igreja no contexto."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        Person.objects.create(name='M1', status=Person.Status.MEMBER)
        Person.objects.create(name='V1', status=Person.Status.VISITOR)

    tenant_client.force_login(pastor)
    resp = tenant_client.get(PASTOR_URL)
    assert resp.status_code == 200
    metrics = resp.context['metrics']
    assert metrics['scope'] == 'church'
    assert metrics['people_total'] == 2


# --------------------------------------------------------------------------- #
# Caminho feliz + escopo — Lider (comunidade)
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
def test_leader_sees_only_own_community(tenant_client, church_a):
    """Lider ve numeros so da(s) sua(s) comunidade(s) — sem vazamento intra-tenant."""
    leader = _user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='Lider', user_id=leader.id)
        led = Community.objects.create(name='Minha', is_active=True)
        led.leaders.add(person)
        other = Community.objects.create(name='Alheia', is_active=True)

        Person.objects.create(name='M1', community=led, status=Person.Status.MEMBER)
        Person.objects.create(name='M2', community=led, status=Person.Status.MEMBER)
        Person.objects.create(name='O1', community=other, status=Person.Status.MEMBER)

        g = Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY,
            date=timezone.now().date(),
            community=led,
        )
        _present(Person.objects.create(name='X', community=led), g)

    tenant_client.force_login(leader)
    resp = tenant_client.get(LEADER_URL)
    assert resp.status_code == 200
    metrics = resp.context['metrics']
    assert metrics['scope'] == 'community'
    assert metrics['people_total'] == 3  # M1, M2, X (todos de 'led'); O1 nao
    assert metrics['attendance_last_month'] == 1


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_leader_without_community_sees_zeros(tenant_client, church_a):
    """Lider sem comunidade vinculada ve zeros — nunca cai para a visao completa."""
    leader = _user(church_a, 'lone@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        Person.objects.create(name='M1', status=Person.Status.MEMBER)
        Community.objects.create(name='C', is_active=True)

    tenant_client.force_login(leader)
    resp = tenant_client.get(LEADER_URL)
    assert resp.status_code == 200
    metrics = resp.context['metrics']
    assert metrics['people_total'] == 0
    assert metrics['active_communities'] == 0


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_pastor_sees_full_on_leader_dashboard(tenant_client, church_a):
    """Pastor no dashboard simplificado curto-circuita para a visao completa (§3.9)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        Person.objects.create(name='M1', status=Person.Status.MEMBER)
        Person.objects.create(name='M2', status=Person.Status.MEMBER)

    tenant_client.force_login(pastor)
    resp = tenant_client.get(LEADER_URL)
    assert resp.status_code == 200
    assert resp.context['metrics']['scope'] == 'church'
    assert resp.context['metrics']['people_total'] == 2


# --------------------------------------------------------------------------- #
# Caminho feliz + escopo — Coordenador (ministerio)
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
def test_coordinator_sees_only_own_ministry(tenant_client, church_a):
    """Coordenador (`leader` num ministerio) ve so o(s) seu(s) ministerio(s)."""
    coordinator = _user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='Coord', user_id=coordinator.id)
        mine = Ministry.objects.create(name='Louvor', is_active=True)
        mine.coordinators.add(person)
        other = Ministry.objects.create(name='Diaconia', is_active=True)

        p1 = Person.objects.create(name='P1', status=Person.Status.MEMBER)
        p2 = Person.objects.create(name='P2', status=Person.Status.MEMBER)
        out = Person.objects.create(name='OX', status=Person.Status.MEMBER)
        p1.ministries.add(mine)
        p2.ministries.add(mine)
        out.ministries.add(other)

    tenant_client.force_login(coordinator)
    resp = tenant_client.get(COORDINATOR_URL)
    assert resp.status_code == 200
    metrics = resp.context['metrics']
    assert metrics['scope'] == 'ministry'
    assert metrics['people_total'] == 2  # p1, p2; OX (outro ministerio) nao


# --------------------------------------------------------------------------- #
# Sem vazamento cross-tenant
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
def test_dashboard_scoped_no_leak(tenant_client, church_a, church_b):
    """Metrica escopada de A nao inclui outra comunidade nem outro tenant."""
    leader = _user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='Lider', user_id=leader.id)
        led = Community.objects.create(name='Minha A', is_active=True)
        led.leaders.add(person)
        other = Community.objects.create(name='Alheia A', is_active=True)
        Person.objects.create(name='AM', community=led, status=Person.Status.MEMBER)
        Person.objects.create(name='AO', community=other, status=Person.Status.MEMBER)

    # Tenant B tem MUITAS pessoas — nenhuma pode vazar para a metrica de A.
    with schema_context(church_b.schema_name):
        for i in range(5):
            Person.objects.create(name=f'B{i}', status=Person.Status.MEMBER)

    tenant_client.force_login(leader)
    resp = tenant_client.get(LEADER_URL)
    assert resp.status_code == 200
    # So a pessoa da comunidade liderada em A — nada de 'other' nem do tenant B.
    assert resp.context['metrics']['people_total'] == 1


# --------------------------------------------------------------------------- #
# Gate de papel
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('roles', [['leader'], ['treasurer'], ['member']])
def test_non_pastor_cannot_access_full_dashboard(tenant_client, church_a, roles):
    """Lider/Tesoureiro/Membro => 403 no dashboard completo (Pastor-only, §3.9)."""
    user = _user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    resp = tenant_client.get(PASTOR_URL)
    assert resp.status_code == 403


@stub_templates
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('url', [LEADER_URL, COORDINATOR_URL])
def test_member_cannot_access_simplified_dashboards(tenant_client, church_a, url):
    """Membro => 403 nos dashboards simplificados (§3.9)."""
    member = _user(church_a, 'member@a.com', ['member'])
    tenant_client.force_login(member)
    resp = tenant_client.get(url)
    assert resp.status_code == 403


@stub_templates
@pytest.mark.django_db(transaction=True)
def test_anonymous_redirected_to_login(tenant_client, church_a):
    """Sem login => redirect (LoginRequiredMixin via TenantRequiredMixin)."""
    resp = tenant_client.get(PASTOR_URL)
    assert resp.status_code == 302
