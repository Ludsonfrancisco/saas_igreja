"""Sprint 6.5 / Bloco 5.3 — magic-link do voluntário (OD-022).

Cobre o token assinado (roundtrip, bind de tenant, expiração, adulteração) e a
view PÚBLICA read-only: mostra só as escalas FUTURAS da própria pessoa, rejeita
pessoa anonimizada / token de outro tenant, emite SecurityLog e não aceita POST.
"""

import datetime

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.core.models import SecurityLog
from apps.gatherings.models import Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person
from apps.schedules.models import Schedule
from apps.schedules.tokens import make_volunteer_token, read_volunteer_token

FUTURE = datetime.date.today() + datetime.timedelta(days=7)
PAST = datetime.date.today() - datetime.timedelta(days=7)


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _scheduled_person(name='Ana', date=FUTURE, role='Vocal'):
    """Cria pessoa + ministério + encontro + escala no schema atual. Retorna a pessoa."""
    ministry = Ministry.objects.create(name='Louvor')
    person = Person.objects.create(name=name)
    person.ministries.add(ministry)
    gathering = Gathering.objects.create(
        gathering_type='worship', date=date, title='Culto'
    )
    Schedule.objects.create(
        ministry=ministry, person=person, gathering=gathering, role=role
    )
    return person


def _url(token):
    return f'/voluntario/escala/{token}/'


# --- Token (unidade) ---------------------------------------------------------


def test_token_roundtrip():
    token = make_volunteer_token(person_id=42, tenant='tenant_a')
    assert read_volunteer_token(token, tenant='tenant_a', max_age=3600) == 42


def test_token_rejected_for_other_tenant():
    token = make_volunteer_token(person_id=42, tenant='tenant_b')
    assert read_volunteer_token(token, tenant='tenant_a', max_age=3600) is None


def test_token_expired_returns_none():
    token = make_volunteer_token(person_id=42, tenant='tenant_a')
    assert read_volunteer_token(token, tenant='tenant_a', max_age=-1) is None


def test_token_tampered_returns_none():
    token = make_volunteer_token(person_id=42, tenant='tenant_a')
    assert read_volunteer_token(token + 'x', tenant='tenant_a', max_age=3600) is None
    assert read_volunteer_token('garbage', tenant='tenant_a', max_age=3600) is None


# --- View (integração) -------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_volunteer_valid_token_shows_own_future_schedule(tenant_client, church_a):
    with schema_context(church_a.schema_name):
        person = _scheduled_person()
        token = make_volunteer_token(person_id=person.pk, tenant=church_a.schema_name)
    resp = tenant_client.get(_url(token))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'Ana' in body
    assert 'Louvor' in body


@pytest.mark.django_db(transaction=True)
def test_volunteer_hides_past_and_others_schedules(tenant_client, church_a):
    with schema_context(church_a.schema_name):
        person = _scheduled_person(name='Ana', date=PAST)  # escala passada
        other = _scheduled_person(name='Bruno', date=FUTURE)  # de outra pessoa
        token = make_volunteer_token(person_id=person.pk, tenant=church_a.schema_name)
    resp = tenant_client.get(_url(token))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'Bruno' not in body  # não vaza escala de terceiros
    assert 'Nenhuma escala futura' in body  # a dela é passada → vazio


@pytest.mark.django_db(transaction=True)
def test_volunteer_garbage_token_is_invalid(tenant_client, church_a):
    resp = tenant_client.get(_url('not-a-real-token'))
    assert resp.status_code == 404
    assert 'Link inválido' in resp.content.decode()


@pytest.mark.django_db(transaction=True)
def test_volunteer_anonymized_person_is_invalid(tenant_client, church_a):
    from django.utils import timezone

    with schema_context(church_a.schema_name):
        person = _scheduled_person()
        person.anonymized_at = timezone.now()
        person.save(update_fields=['anonymized_at'])
        token = make_volunteer_token(person_id=person.pk, tenant=church_a.schema_name)
    resp = tenant_client.get(_url(token))
    assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_volunteer_cross_tenant_token_rejected(tenant_client, church_a):
    """Token assinado para outro tenant não resolve no subdomínio de A."""
    with schema_context(church_a.schema_name):
        person = _scheduled_person()
    token = make_volunteer_token(person_id=person.pk, tenant='tenant_b')
    resp = tenant_client.get(_url(token))
    assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_volunteer_access_emits_security_log(tenant_client, church_a):
    with schema_context(church_a.schema_name):
        person = _scheduled_person()
        token = make_volunteer_token(person_id=person.pk, tenant=church_a.schema_name)
    tenant_client.get(_url(token))
    with schema_context(church_a.schema_name):
        log = SecurityLog.objects.filter(event_type='volunteer_schedule_access').first()
        assert log is not None
        assert log.payload.get('person_id') == person.pk


@pytest.mark.django_db(transaction=True)
def test_volunteer_view_is_read_only(tenant_client, church_a):
    with schema_context(church_a.schema_name):
        person = _scheduled_person()
        token = make_volunteer_token(person_id=person.pk, tenant=church_a.schema_name)
    assert tenant_client.post(_url(token)).status_code == 405
