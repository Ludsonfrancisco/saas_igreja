"""Sprint 4 / Frente 2 — view de Presença (ACCESS_MATRIX §3.6 / RN-009).

Cobre: barreira de papel + escopo por encontro (Pastor/Secretário qualquer; Líder
só o que cria/lidera; fora → 404; Membro → 403), fluxo POST de marcação em lote, e
o pré-check dos já-presentes no GET.
"""

import datetime

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.gatherings.models import Attendance, Gathering
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _gathering(church, **extra):
    with schema_context(church.schema_name):
        return Gathering.objects.create(
            gathering_type=extra.pop('gtype', 'worship'),
            date=datetime.date(2026, 6, 10),
            **extra,
        )


# --- Barreira de papel + escopo ----------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_member_cannot_access_attendance(tenant_client, church_a):
    member = _make_user(church_a, 'member@a.com', ['member'])
    g = _gathering(church_a, created_by=999)
    tenant_client.force_login(member)
    assert tenant_client.get(f'/encontros/{g.pk}/presenca/').status_code == 403


@pytest.mark.django_db(transaction=True)
def test_pastor_can_mark_any(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    g = _gathering(church_a, created_by=999)
    tenant_client.force_login(pastor)
    assert tenant_client.get(f'/encontros/{g.pk}/presenca/').status_code == 200


@pytest.mark.django_db(transaction=True)
def test_leader_foreign_gathering_404(tenant_client, church_a):
    """Líder sem vínculo com o encontro (não criou, não é sua comunidade) → 404."""
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    g = _gathering(church_a, created_by=999)
    tenant_client.force_login(leader)
    assert tenant_client.get(f'/encontros/{g.pk}/presenca/').status_code == 404


@pytest.mark.django_db(transaction=True)
def test_leader_own_community_gathering_ok(tenant_client, church_a):
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='Lider', user_id=leader.id)
        community = Community.objects.create(name='Minha')
        community.leaders.add(person)
        g = Gathering.objects.create(
            gathering_type='community',
            date=datetime.date(2026, 6, 10),
            community=community,
            created_by=999,
        )
    tenant_client.force_login(leader)
    assert tenant_client.get(f'/encontros/{g.pk}/presenca/').status_code == 200


# --- Fluxo de marcação --------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_post_marks_present_in_bulk(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        g = Gathering.objects.create(
            gathering_type='worship', date=datetime.date(2026, 6, 10)
        )
        p1 = Person.objects.create(name='A')
        p2 = Person.objects.create(name='B')
    tenant_client.force_login(pastor)
    resp = tenant_client.post(
        f'/encontros/{g.pk}/presenca/', {'present': [str(p1.pk), str(p2.pk)]}
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        assert Attendance.objects.filter(gathering=g, is_present=True).count() == 2


@pytest.mark.django_db(transaction=True)
def test_get_prechecks_present(tenant_client, church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        g = Gathering.objects.create(
            gathering_type='worship', date=datetime.date(2026, 6, 10)
        )
        p1 = Person.objects.create(name='A')
        Attendance.objects.create(gathering=g, person=p1, is_present=True)
    tenant_client.force_login(pastor)
    resp = tenant_client.get(f'/encontros/{g.pk}/presenca/')
    assert resp.status_code == 200
    assert p1.pk in resp.context['present_ids']
