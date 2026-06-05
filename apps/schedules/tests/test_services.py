"""Sprint 5 / Frente 1 — service de Escalas (vínculo + bloqueio de conflito, §3.7).

Regra de negócio pura dentro do schema do tenant. Person/Ministry/Gathering/Schedule
vivem no tenant (TENANT-04).
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

from apps.gatherings.models import Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person
from apps.schedules import services

DATE = datetime.date(2026, 6, 14)


def _ministry_with_member(name='Louvor', member_name='Ana'):
    ministry = Ministry.objects.create(name=name)
    member = Person.objects.create(name=member_name)
    member.ministries.add(ministry)
    return ministry, member


def _gathering(date=DATE, gtype=Gathering.Type.WORSHIP, title='Culto'):
    return Gathering.objects.create(gathering_type=gtype, date=date, title=title)


# --- vínculo ao ministério ---------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_create_schedule_validates_ministry_membership(church_a):
    with schema_context(church_a.schema_name):
        ministry = Ministry.objects.create(name='Louvor')
        outsider = Person.objects.create(name='Fora')  # NÃO está no ministério
        gathering = _gathering()
        with pytest.raises(ValidationError):
            services.create_schedule(
                ministry=ministry, person=outsider, gathering=gathering
            )


@pytest.mark.django_db(transaction=True)
def test_create_schedule_success(church_a):
    with schema_context(church_a.schema_name):
        ministry, member = _ministry_with_member()
        gathering = _gathering()
        schedule = services.create_schedule(
            ministry=ministry, person=member, gathering=gathering, role='Vocal'
        )
        assert schedule.pk is not None
        assert schedule.role == 'Vocal'


# --- bloqueio de conflito ----------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_create_schedule_blocks_conflict_same_date_other_gathering(church_a):
    with schema_context(church_a.schema_name):
        ministry, member = _ministry_with_member()
        g1 = _gathering(title='Culto manha')
        g2 = _gathering(title='Culto noite')  # mesma data, outro encontro
        services.create_schedule(ministry=ministry, person=member, gathering=g1)
        with pytest.raises(ValidationError):
            services.create_schedule(ministry=ministry, person=member, gathering=g2)


@pytest.mark.django_db(transaction=True)
def test_create_schedule_allow_conflict_overrides(church_a):
    """`allow_conflict=True` (usado pela aprovação) cria mesmo com conflito."""
    with schema_context(church_a.schema_name):
        ministry, member = _ministry_with_member()
        g1 = _gathering(title='Culto manha')
        g2 = _gathering(title='Culto noite')
        services.create_schedule(ministry=ministry, person=member, gathering=g1)
        schedule = services.create_schedule(
            ministry=ministry, person=member, gathering=g2, allow_conflict=True
        )
        assert schedule.pk is not None


@pytest.mark.django_db(transaction=True)
def test_no_conflict_same_gathering_two_ministries(church_a):
    """Mesma pessoa no MESMO encontro, ministérios distintos, não é conflito."""
    with schema_context(church_a.schema_name):
        louvor, member = _ministry_with_member(name='Louvor')
        som = Ministry.objects.create(name='Som')
        member.ministries.add(som)
        gathering = _gathering()
        services.create_schedule(ministry=louvor, person=member, gathering=gathering)
        # mesmo encontro, outro ministério → sem conflito
        schedule = services.create_schedule(
            ministry=som, person=member, gathering=gathering
        )
        assert schedule.pk is not None


@pytest.mark.django_db(transaction=True)
def test_detect_conflict_returns_conflicting(church_a):
    with schema_context(church_a.schema_name):
        ministry, member = _ministry_with_member()
        g1 = _gathering(title='A')
        g2 = _gathering(title='B')
        services.create_schedule(ministry=ministry, person=member, gathering=g1)
        conflicts = services.detect_conflict(person=member, gathering=g2)
        assert conflicts.count() == 1


@pytest.mark.django_db(transaction=True)
def test_person_hard_delete_preserves_schedule_set_null(church_a):
    """RN-007 / OD-020: purge da Pessoa preserva a escala (person=NULL)."""
    with schema_context(church_a.schema_name):
        ministry, member = _ministry_with_member()
        gathering = _gathering()
        schedule = services.create_schedule(
            ministry=ministry, person=member, gathering=gathering
        )
        member.delete()
        schedule.refresh_from_db()
        assert schedule.person_id is None
