"""Comunidades v2 / Bloco 2 — view de lançamento de presença da célula (RF-108).

Cobre `CommunitySessionView`: o Líder da célula lança presença (membros + visitante +
nota), persistindo `Attendance` + `AttendanceSession`. Escopo: célula que não é do
Líder ou encontro de outra célula => 404 (não vaza, RISK-001).
"""

import datetime

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.gatherings.models import AttendanceSession, Gathering
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
TODAY = datetime.date(2026, 6, 10)


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _session_url(community_pk, gathering_pk):
    return f'/comunidades/{community_pk}/lancamento/{gathering_pk}/'


@pytest.mark.django_db(transaction=True)
def test_leader_launches_cell_session(tenant_client, church_a):
    """Líder lança presença da célula: membro presente + visitante + nota → 302."""
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        leader_person = Person.objects.create(name='Lider', user_id=leader.id)
        cell = Community.objects.create(name='Minha Célula')
        cell.leaders.add(leader_person)
        ana = Person.objects.create(name='Ana', community=cell)
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY, date=TODAY, community=cell
        )
        cell_pk, gid, ana_pk = cell.pk, gathering.pk, ana.pk

    tenant_client.force_login(leader)
    assert tenant_client.get(_session_url(cell_pk, gid)).status_code == 200

    resp = tenant_client.post(
        _session_url(cell_pk, gid),
        {'present': [ana_pk], 'visitors': 'João Visita', 'note': 'Estudo bom.'},
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        session = AttendanceSession.objects.get(gathering_id=gid)
        assert session.note == 'Estudo bom.'
        assert session.confirmed_by == leader.id
        assert gathering.attendances.filter(person_id=ana_pk, is_present=True).exists()
        visitor = Person.objects.get(name='João Visita')
        assert visitor.status == Person.Status.VISITOR
        assert visitor.community_id == cell_pk


@pytest.mark.django_db(transaction=True)
def test_leader_cannot_launch_other_cell(tenant_client, church_a):
    """Célula que o Líder não lidera → 404 (não vaza)."""
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        leader_person = Person.objects.create(name='Lider', user_id=leader.id)
        mine = Community.objects.create(name='Minha')
        mine.leaders.add(leader_person)
        other = Community.objects.create(name='Outra')
        g_other = Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY, date=TODAY, community=other
        )
        other_pk, gid = other.pk, g_other.pk

    tenant_client.force_login(leader)
    assert tenant_client.get(_session_url(other_pk, gid)).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_gathering_must_belong_to_community(tenant_client, church_a):
    """Encontro de OUTRA célula passado na URL da minha → 404."""
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        leader_person = Person.objects.create(name='Lider', user_id=leader.id)
        mine = Community.objects.create(name='Minha')
        mine.leaders.add(leader_person)
        other = Community.objects.create(name='Outra')
        g_other = Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY, date=TODAY, community=other
        )
        mine_pk, gid = mine.pk, g_other.pk

    tenant_client.force_login(leader)
    assert tenant_client.get(_session_url(mine_pk, gid)).status_code == 404
