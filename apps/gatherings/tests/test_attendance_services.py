"""Sprint 4 / Frente 2 — service de Presença (RN-009 / RN-007 / §3.6).

Regra de negócio pura (roster, marcação em lote idempotente, escopo de marcação)
dentro do schema do tenant. O ator (`User`) é público; Person/Gathering/Attendance
vivem no tenant (TENANT-04).
"""

import datetime

import pytest
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.gatherings import services
from apps.gatherings.models import Attendance, Gathering
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
TODAY = datetime.date(2026, 6, 10)


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


# --- roster ------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_roster_community_gathering_lists_only_members(church_a):
    with schema_context(church_a.schema_name):
        community = Community.objects.create(name='Celula')
        inside = Person.objects.create(name='Dentro', community=community)
        Person.objects.create(name='Fora')
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY, date=TODAY, community=community
        )
        roster = list(services.attendance_roster(gathering))
    assert roster == [inside]


@pytest.mark.django_db(transaction=True)
def test_roster_non_community_lists_active_excludes_inactive(church_a):
    with schema_context(church_a.schema_name):
        active = Person.objects.create(name='Ativa', status=Person.Status.MEMBER)
        Person.objects.create(name='Inativa', status=Person.Status.INACTIVE)
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=TODAY
        )
        roster = list(services.attendance_roster(gathering))
    assert roster == [active]


@pytest.mark.django_db(transaction=True)
def test_roster_excludes_anonymized(church_a):
    from django.utils import timezone

    with schema_context(church_a.schema_name):
        Person.objects.create(
            name='Anon', status=Person.Status.MEMBER, anonymized_at=timezone.now()
        )
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=TODAY
        )
        roster = list(services.attendance_roster(gathering))
    assert roster == []


# --- mark_attendance_bulk (RN-009) -------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_bulk_mark_creates_present(church_a):
    with schema_context(church_a.schema_name):
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=TODAY
        )
        p1 = Person.objects.create(name='A')
        p2 = Person.objects.create(name='B')
        count = services.mark_attendance_bulk(
            gathering=gathering, present_person_ids=[p1.id, p2.id]
        )
        assert count == 2
        assert (
            Attendance.objects.filter(gathering=gathering, is_present=True).count() == 2
        )


@pytest.mark.django_db(transaction=True)
def test_bulk_mark_idempotent_no_duplicate(church_a):
    """RN-009: marcar duas vezes não duplica (unique + update_or_create)."""
    with schema_context(church_a.schema_name):
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=TODAY
        )
        p1 = Person.objects.create(name='A')
        services.mark_attendance_bulk(gathering=gathering, present_person_ids=[p1.id])
        services.mark_attendance_bulk(gathering=gathering, present_person_ids=[p1.id])
        assert Attendance.objects.filter(gathering=gathering, person=p1).count() == 1


@pytest.mark.django_db(transaction=True)
def test_bulk_mark_unchecked_flips_to_absent_keeps_row(church_a):
    with schema_context(church_a.schema_name):
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=TODAY
        )
        p1 = Person.objects.create(name='A')
        services.mark_attendance_bulk(gathering=gathering, present_person_ids=[p1.id])
        # segunda marcação sem p1: vira ausente, mas a linha permanece.
        services.mark_attendance_bulk(gathering=gathering, present_person_ids=[])
        att = Attendance.objects.get(gathering=gathering, person=p1)
        assert att.is_present is False


@pytest.mark.django_db(transaction=True)
def test_bulk_mark_ignores_unknown_ids(church_a):
    """Ids inexistentes são ignorados (não cria linha, não quebra)."""
    with schema_context(church_a.schema_name):
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=TODAY
        )
        count = services.mark_attendance_bulk(
            gathering=gathering, present_person_ids=[999999]
        )
        assert count == 0
        assert Attendance.objects.filter(gathering=gathering).count() == 0


# --- RN-007 / OD-020: SET_NULL preserva presença -----------------------------


@pytest.mark.django_db(transaction=True)
def test_person_hard_delete_preserves_attendance_set_null(church_a):
    """Purge físico (delete) da Pessoa preserva o registro de presença (person=NULL)."""
    with schema_context(church_a.schema_name):
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=TODAY
        )
        p1 = Person.objects.create(name='A')
        services.mark_attendance_bulk(gathering=gathering, present_person_ids=[p1.id])
        p1.delete()
        att = Attendance.objects.get(gathering=gathering)
        assert att.person_id is None
        assert att.is_present is True


# --- can_mark_attendance (escopo §3.6) ---------------------------------------


@pytest.mark.django_db(transaction=True)
def test_can_mark_admin_any_gathering(church_a):
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    sec = _make_user(church_a, 'sec@a.com', ['secretary'])
    with schema_context(church_a.schema_name):
        gathering = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=TODAY, created_by=999
        )
        assert services.can_mark_attendance(pastor, gathering) is True
        assert services.can_mark_attendance(sec, gathering) is True


@pytest.mark.django_db(transaction=True)
def test_can_mark_leader_own_creation_and_own_community(church_a):
    leader = _make_user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        person = Person.objects.create(name='Lider', user_id=leader.id)
        community = Community.objects.create(name='Minha')
        community.leaders.add(person)
        own = Gathering.objects.create(
            gathering_type=Gathering.Type.EVENT, date=TODAY, created_by=leader.id
        )
        community_g = Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY,
            date=TODAY,
            community=community,
            created_by=999,
        )
        foreign = Gathering.objects.create(
            gathering_type=Gathering.Type.EVENT, date=TODAY, created_by=999
        )
        assert services.can_mark_attendance(leader, own) is True
        assert services.can_mark_attendance(leader, community_g) is True
        assert services.can_mark_attendance(leader, foreign) is False
