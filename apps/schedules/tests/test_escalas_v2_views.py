"""Escalas v2 — Bloco 2 (frontend): tela de eventos + modal de escalação + opt-out.

RF-111..114. Usa o client tenant-scoped (HTTP_HOST='a.testserver' → church_a).
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
from apps.schedules.models import MinistryEventOptOut, Schedule

GOOD_PASSWORD = 'Senha@123'
EVENTS_URL = '/escalas/eventos/'
TODAY_MONTH = datetime.date.today().replace(day=15)


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _ministry(name='Louvor', member_name='Ana', coord_user=None):
    ministry = Ministry.objects.create(name=name)
    member = Person.objects.create(name=member_name)
    member.ministries.add(ministry)
    if coord_user is not None:
        coord = Person.objects.create(name='Coord', user_id=coord_user.id)
        ministry.coordinators.add(coord)
    return ministry, member


def _event(title='Culto'):
    return Gathering.objects.create(
        gathering_type='worship', date=TODAY_MONTH, title=title
    )


@pytest.mark.django_db(transaction=True)
def test_events_page_renders_with_event(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        _ministry()
        _event(title='Culto Domingo')
    tenant_client.force_login(pastor)
    resp = tenant_client.get(EVENTS_URL)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'Culto Domingo' in html
    assert 'Escalar' in html


@pytest.mark.django_db(transaction=True)
def test_event_modal_renders_roster(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        _ministry(member_name='Ana')
        event = _event()
    tenant_client.force_login(pastor)
    resp = tenant_client.get(f'/escalas/eventos/{event.pk}/escalar/')
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'Louvor' in html
    assert 'Ana' in html
    assert 'name="person_ids"' in html  # checkbox de escalação


@pytest.mark.django_db(transaction=True)
def test_event_modal_post_schedules_members(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        ministry, member = _ministry(member_name='Ana')
        event = _event()
    tenant_client.force_login(pastor)
    resp = tenant_client.post(
        f'/escalas/eventos/{event.pk}/escalar/',
        {'ministry': ministry.pk, 'person_ids': [member.pk]},
    )
    assert resp.status_code == 200
    assert 'Escalado' in resp.content.decode()
    with schema_context(church_a.schema_name):
        assert Schedule.objects.filter(
            ministry=ministry, person=member, gathering=event
        ).exists()


@pytest.mark.django_db(transaction=True)
def test_event_modal_greys_conflicted_member(tenant_client, church_a):
    """RF-113: membro já escalado em outro encontro na data → 'escalar mesmo assim'."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        ministry, member = _ministry(member_name='Ana')
        target = _event(title='Culto noite')
        other = _event(title='Culto manha')
        Schedule.objects.create(ministry=ministry, person=member, gathering=other)
    tenant_client.force_login(pastor)
    resp = tenant_client.get(f'/escalas/eventos/{target.pk}/escalar/')
    html = resp.content.decode()
    assert 'escalar mesmo assim' in html
    assert 'já escalado nessa data' in html


@pytest.mark.django_db(transaction=True)
def test_coordinator_optout_set_and_clear(tenant_client, church_a):
    """RF-114/RN-022: o coordenador marca opt-out e depois remove."""
    coord = _user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        ministry, _ = _ministry(coord_user=coord)
        event = _event()
    tenant_client.force_login(coord)
    base = f'/escalas/eventos/{event.pk}/ministerio/{ministry.pk}/atuacao/'

    set_resp = tenant_client.post(base, {'action': 'set'})
    assert set_resp.status_code == 200
    with schema_context(church_a.schema_name):
        assert MinistryEventOptOut.objects.filter(
            ministry=ministry, gathering=event
        ).exists()

    clear_resp = tenant_client.post(base, {'action': 'clear'})
    assert clear_resp.status_code == 200
    with schema_context(church_a.schema_name):
        assert not MinistryEventOptOut.objects.filter(
            ministry=ministry, gathering=event
        ).exists()


@pytest.mark.django_db(transaction=True)
def test_pastor_cannot_set_optout_rn022(tenant_client, church_a):
    """RN-022: Pastor (não coordenador) não marca opt-out → 404 (não revela)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        ministry, _ = _ministry()  # sem coordenador vinculado ao pastor
        event = _event()
    tenant_client.force_login(pastor)
    resp = tenant_client.post(
        f'/escalas/eventos/{event.pk}/ministerio/{ministry.pk}/atuacao/',
        {'action': 'set'},
    )
    assert resp.status_code == 404
    with schema_context(church_a.schema_name):
        assert not MinistryEventOptOut.objects.filter(ministry=ministry).exists()


@pytest.mark.django_db(transaction=True)
def test_member_blocked_from_events_page(tenant_client, church_a):
    """Barreira de papel: Membro não acessa a tela de Escalas (403)."""
    member = _user(church_a, 'member@a.com', ['member'])
    tenant_client.force_login(member)
    assert tenant_client.get(EVENTS_URL).status_code == 403
