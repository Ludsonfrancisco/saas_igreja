"""Sprint 5 / Frente 1 — views CRUD de Escala (ACCESS_MATRIX §3.7).

Cobre: barreira de papel (Membro 403), criação via service, bloqueio de conflito
pela view, escopo de Coordenador (só o seu ministério → 404 fora), Secretário admin
no CRUD (cria + exclui).
"""

import datetime

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.gatherings.models import Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person
from apps.schedules.models import Schedule, ScheduleConflictApproval

GOOD_PASSWORD = 'Senha@123'
LIST_URL = '/escalas/'
CREATE_URL = '/escalas/nova/'
EXCEPTION_URL = '/escalas/excecao/nova/'
DATE = datetime.date(2026, 6, 14)


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _ministry_with_member(name='Louvor', member_name='Ana', coord_user=None):
    ministry = Ministry.objects.create(name=name)
    member = Person.objects.create(name=member_name)
    member.ministries.add(ministry)
    if coord_user is not None:
        coord_person = Person.objects.create(name='Coord', user_id=coord_user.id)
        ministry.coordinators.add(coord_person)
    return ministry, member


# --- Barreira de papel -------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected',
    [(['pastor'], 200), (['secretary'], 200), (['leader'], 200), (['member'], 403)],
)
def test_schedule_list_role_barrier(tenant_client, church_a, roles, expected):
    user = _make_user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    assert tenant_client.get(LIST_URL).status_code == expected


# --- Criação -----------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_pastor_creates_schedule(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        ministry, member = _ministry_with_member()
        gathering = Gathering.objects.create(
            gathering_type='worship', date=DATE, title='Culto'
        )
    tenant_client.force_login(pastor)
    resp = tenant_client.post(
        CREATE_URL,
        {
            'ministry': ministry.pk,
            'person': member.pk,
            'gathering': gathering.pk,
            'role': 'Vocal',
            'notes': '',
        },
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        assert Schedule.objects.filter(person=member, ministry=ministry).exists()


@pytest.mark.django_db(transaction=True)
def test_create_blocked_by_conflict_via_view(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        ministry, member = _ministry_with_member()
        g1 = Gathering.objects.create(gathering_type='worship', date=DATE, title='M')
        g2 = Gathering.objects.create(gathering_type='event', date=DATE, title='N')
        Schedule.objects.create(ministry=ministry, person=member, gathering=g1)
    tenant_client.force_login(pastor)
    resp = tenant_client.post(
        CREATE_URL,
        {'ministry': ministry.pk, 'person': member.pk, 'gathering': g2.pk, 'notes': ''},
    )
    assert resp.status_code == 200  # form re-renderizado com erro de conflito
    with schema_context(church_a.schema_name):
        assert not Schedule.objects.filter(gathering=g2).exists()


# --- Escopo de Coordenador ---------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_coordinator_sees_only_own_ministry(tenant_client, church_a):
    coord = _make_user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        mine, mine_member = _ministry_with_member(name='Louvor', coord_user=coord)
        gathering = Gathering.objects.create(
            gathering_type='worship', date=DATE, title='Culto'
        )
        mine_schedule = Schedule.objects.create(
            ministry=mine, person=mine_member, gathering=gathering
        )
        other, other_member = _ministry_with_member(name='Som', member_name='Beto')
        other_schedule = Schedule.objects.create(
            ministry=other, person=other_member, gathering=gathering
        )
    tenant_client.force_login(coord)
    assert tenant_client.get(f'/escalas/{mine_schedule.pk}/').status_code == 200
    assert tenant_client.get(f'/escalas/{other_schedule.pk}/').status_code == 404


@pytest.mark.django_db(transaction=True)
def test_coordinator_deletes_own_ministry_schedule(tenant_client, church_a):
    coord = _make_user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        mine, member = _ministry_with_member(name='Louvor', coord_user=coord)
        gathering = Gathering.objects.create(
            gathering_type='worship', date=DATE, title='Culto'
        )
        schedule = Schedule.objects.create(
            ministry=mine, person=member, gathering=gathering
        )
    tenant_client.force_login(coord)
    resp = tenant_client.post(f'/escalas/{schedule.pk}/excluir/')
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        assert not Schedule.objects.filter(pk=schedule.pk).exists()


# --- Secretário admin --------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_secretary_creates_and_deletes(tenant_client, church_a):
    secretary = _make_user(church_a, 'sec@a.com', ['secretary'])
    with schema_context(church_a.schema_name):
        ministry, member = _ministry_with_member()
        gathering = Gathering.objects.create(
            gathering_type='worship', date=DATE, title='Culto'
        )
    tenant_client.force_login(secretary)
    resp = tenant_client.post(
        CREATE_URL,
        {
            'ministry': ministry.pk,
            'person': member.pk,
            'gathering': gathering.pk,
            'notes': '',
        },
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        schedule = Schedule.objects.get(person=member)
    assert tenant_client.post(f'/escalas/{schedule.pk}/excluir/').status_code == 302


# --- Aprovação de exceção de conflito (Frente 2, §3.7) -----------------------


def _conflict_setup(coord_user=None):
    """Conflito pronto: `member` já escalado em `g1` na DATE; `g2` (mesma data,
    outro encontro) é o conflito que a exceção autoriza."""
    ministry, member = _ministry_with_member(coord_user=coord_user)
    g1 = Gathering.objects.create(gathering_type='worship', date=DATE, title='Manha')
    g2 = Gathering.objects.create(gathering_type='event', date=DATE, title='Noite')
    Schedule.objects.create(ministry=ministry, person=member, gathering=g1)
    return ministry, member, g2


@pytest.mark.django_db(transaction=True)
def test_secretary_cannot_approve_exception(tenant_client, church_a):
    """Secretário é admin no CRUD, mas NÃO aprova exceção (gate de papel → 403)."""
    secretary = _make_user(church_a, 'sec@a.com', ['secretary'])
    tenant_client.force_login(secretary)
    assert tenant_client.get(EXCEPTION_URL).status_code == 403


@pytest.mark.django_db(transaction=True)
def test_competent_coordinator_approves_exception_via_view(tenant_client, church_a):
    """Coordenador competente aprova exceção pela view → 302 + aprovação registrada."""
    coord = _make_user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        ministry, member, g2 = _conflict_setup(coord_user=coord)
    tenant_client.force_login(coord)
    resp = tenant_client.post(
        EXCEPTION_URL,
        {
            'ministry': ministry.pk,
            'person': member.pk,
            'gathering': g2.pk,
            'role': '',
            'notes': '',
            'justification': 'Coordenador autoriza o acumulo.',
        },
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        schedule = Schedule.objects.get(gathering=g2)
        assert ScheduleConflictApproval.objects.filter(schedule=schedule).exists()


@pytest.mark.django_db(transaction=True)
def test_noncompetent_leader_exception_blocked(tenant_client, church_a):
    """Líder que não coordena o ministério passa o gate de papel, mas o ministério
    nem aparece no form (escopo por coordenação) — defesa em profundidade
    (P-ARQ-08; o barramento no service é coberto em test_services). Resultado:
    form re-renderizado (200), nenhuma aprovação criada."""
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        ministry, member, g2 = _conflict_setup()  # sem coordenador vinculado
    tenant_client.force_login(leader)
    resp = tenant_client.post(
        EXCEPTION_URL,
        {
            'ministry': ministry.pk,
            'person': member.pk,
            'gathering': g2.pk,
            'role': '',
            'notes': '',
            'justification': 'Tentativa sem competencia.',
        },
    )
    assert resp.status_code == 200
    with schema_context(church_a.schema_name):
        assert not ScheduleConflictApproval.objects.exists()
