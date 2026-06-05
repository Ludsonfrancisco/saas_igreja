"""Sprint 6 / Bloco 5 — `church_metrics`: contas corretas e recorte por escopo.

Cobertura:
- visao completa (Pastor): totais por status, presenca ultimo mes, comunidades/
  ministerios ativos da igreja inteira;
- recorte por comunidade: so as pessoas/presenca da(s) comunidade(s) do escopo;
- recorte por ministerio: so as pessoas/presenca do(s) ministerio(s) do escopo;
- conservador: escopo VAZIO => metrica zerada (nunca a visao completa);
- janela de presenca (~30 dias): encontro antigo nao conta;
- `people_by_status` traz TODOS os status (inclusive 0).

Models de TENANT_APPS -> `schema_context` para ORM puro. DDL de criar Church exige
`@pytest.mark.django_db(transaction=True)`.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.communities.models import Community
from apps.dashboard.services import church_metrics
from apps.gatherings.models import Attendance, Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person


@pytest.fixture(autouse=True)
def _reset_schema():
    yield
    connection.set_schema_to_public()


def _present(person, gathering):
    return Attendance.objects.create(
        person=person, gathering=gathering, is_present=True
    )


# --------------------------------------------------------------------------- #
# Visao completa (Pastor)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_full_church_metrics(church_a):
    """Sem escopo => numeros da igreja inteira, por status e presenca recente."""
    with schema_context(church_a.schema_name):
        Person.objects.create(name='V1', status=Person.Status.VISITOR)
        Person.objects.create(name='M1', status=Person.Status.MEMBER)
        Person.objects.create(name='M2', status=Person.Status.MEMBER)
        present_person = Person.objects.create(name='P', status=Person.Status.MEMBER)

        Community.objects.create(name='C ativa', is_active=True)
        Community.objects.create(name='C inativa', is_active=False)
        Ministry.objects.create(name='Min ativo', is_active=True)

        recent = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=timezone.now().date()
        )
        _present(present_person, recent)

        metrics = church_metrics()

    assert metrics['scope'] == 'church'
    assert metrics['people_total'] == 4
    assert metrics['people_by_status'][Person.Status.MEMBER] == 3
    assert metrics['people_by_status'][Person.Status.VISITOR] == 1
    # Todos os status presentes no dict, mesmo zerados.
    assert metrics['people_by_status'][Person.Status.INACTIVE] == 0
    assert metrics['attendance_last_month'] == 1
    assert metrics['active_communities'] == 1
    assert metrics['active_ministries'] == 1


@pytest.mark.django_db(transaction=True)
def test_attendance_window_excludes_old_gatherings(church_a):
    """Presenca em encontro fora da janela (~30 dias) nao conta."""
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='P', status=Person.Status.MEMBER)
        old = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP,
            date=timezone.now().date() - timedelta(days=45),
        )
        _present(person, old)

        metrics = church_metrics()

    assert metrics['attendance_last_month'] == 0


@pytest.mark.django_db(transaction=True)
def test_attendance_ignores_absent(church_a):
    """Marcacao com is_present=False nao entra na contagem de presenca."""
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='P', status=Person.Status.MEMBER)
        g = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=timezone.now().date()
        )
        Attendance.objects.create(person=person, gathering=g, is_present=False)

        metrics = church_metrics()

    assert metrics['attendance_last_month'] == 0


# --------------------------------------------------------------------------- #
# Recorte por comunidade
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_community_scope_counts_only_scoped(church_a):
    """`community_ids` recorta pessoas e presenca a(s) comunidade(s) do escopo."""
    with schema_context(church_a.schema_name):
        mine = Community.objects.create(name='Minha', is_active=True)
        other = Community.objects.create(name='Outra', is_active=True)

        Person.objects.create(name='M1', community=mine, status=Person.Status.MEMBER)
        Person.objects.create(name='M2', community=mine, status=Person.Status.MEMBER)
        Person.objects.create(name='O1', community=other, status=Person.Status.MEMBER)
        outside = Person.objects.create(name='O2', community=mine)

        g_mine = Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY,
            date=timezone.now().date(),
            community=mine,
        )
        g_other = Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY,
            date=timezone.now().date(),
            community=other,
        )
        _present(outside, g_mine)
        _present(Person.objects.create(name='OX', community=other), g_other)

        metrics = church_metrics(community_ids=[mine.id])

    assert metrics['scope'] == 'community'
    assert metrics['people_total'] == 3  # M1, M2, O2 — todos da comunidade 'mine'
    assert metrics['attendance_last_month'] == 1  # so a presenca no encontro de mine
    assert metrics['active_communities'] == 1


@pytest.mark.django_db(transaction=True)
def test_empty_community_scope_is_zeroed(church_a):
    """Escopo de comunidade VAZIO => zeros, nunca a visao completa (conservador)."""
    with schema_context(church_a.schema_name):
        Person.objects.create(name='M1', status=Person.Status.MEMBER)
        Community.objects.create(name='C', is_active=True)

        metrics = church_metrics(community_ids=[])

    assert metrics['scope'] == 'community'
    assert metrics['people_total'] == 0
    assert metrics['attendance_last_month'] == 0
    assert metrics['active_communities'] == 0


# --------------------------------------------------------------------------- #
# Recorte por ministerio
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_ministry_scope_counts_only_scoped(church_a):
    """`ministry_ids` recorta pessoas (M2M) e presenca a(s) pessoa(s) do ministerio."""
    with schema_context(church_a.schema_name):
        mine = Ministry.objects.create(name='Louvor', is_active=True)
        other = Ministry.objects.create(name='Diaconia', is_active=True)

        p1 = Person.objects.create(name='P1', status=Person.Status.MEMBER)
        p2 = Person.objects.create(name='P2', status=Person.Status.MEMBER)
        outsider = Person.objects.create(name='OX', status=Person.Status.MEMBER)
        p1.ministries.add(mine)
        p2.ministries.add(mine)
        outsider.ministries.add(other)

        g = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=timezone.now().date()
        )
        _present(p1, g)
        _present(outsider, g)

        metrics = church_metrics(ministry_ids=[mine.id])

    assert metrics['scope'] == 'ministry'
    assert metrics['people_total'] == 2  # p1, p2
    assert metrics['attendance_last_month'] == 1  # so p1 (do ministerio); outsider nao
    assert metrics['active_ministries'] == 1


@pytest.mark.django_db(transaction=True)
def test_empty_ministry_scope_is_zeroed(church_a):
    """Escopo de ministerio VAZIO => zeros (conservador)."""
    with schema_context(church_a.schema_name):
        Person.objects.create(name='P', status=Person.Status.MEMBER)
        Ministry.objects.create(name='Min', is_active=True)

        metrics = church_metrics(ministry_ids=[])

    assert metrics['scope'] == 'ministry'
    assert metrics['people_total'] == 0
    assert metrics['attendance_last_month'] == 0
    assert metrics['active_ministries'] == 0


@pytest.mark.django_db(transaction=True)
def test_person_in_two_scoped_ministries_counted_once(church_a):
    """Pessoa em >1 ministerio do escopo conta UMA vez (distinct no join M2M)."""
    with schema_context(church_a.schema_name):
        m1 = Ministry.objects.create(name='M1', is_active=True)
        m2 = Ministry.objects.create(name='M2', is_active=True)
        p = Person.objects.create(name='P', status=Person.Status.MEMBER)
        p.ministries.add(m1, m2)

        metrics = church_metrics(ministry_ids=[m1.id, m2.id])

    assert metrics['people_total'] == 1
