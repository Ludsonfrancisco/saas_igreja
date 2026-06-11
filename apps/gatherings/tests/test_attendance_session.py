"""Comunidades v2 / Bloco 1 — service de sessão de presença da célula.

Cobre `launch_attendance_session` (RF-108 · DM-1/DM-2) e `cell_pending_days`
(RF-107): marcação em lote + visitante (Person VISITOR) + nota da sessão (RN-016) +
confirmação, e os "dias a lançar" da célula com o flag `is_launched`.

Pura regra de negócio no schema do tenant (TENANT-04): Person/Gathering/Attendance/
AttendanceSession vivem no tenant; o ator (`confirmed_by`) é `user_id` público.
"""

import datetime

import pytest
from django_tenants.utils import schema_context

from apps.gatherings import services
from apps.gatherings.models import Attendance, AttendanceSession, Gathering
from apps.people.models import Person

TODAY = datetime.date(2026, 6, 10)


def _community_gathering(community, date=TODAY):
    return Gathering.objects.create(
        gathering_type=Gathering.Type.COMMUNITY, date=date, community=community
    )


@pytest.mark.django_db(transaction=True)
def test_launch_session_marks_presence_and_confirms(church_a):
    """Lança a sessão: marca presente/ausente + grava nota e confirmação (RN-016)."""
    from apps.communities.models import Community

    with schema_context(church_a.schema_name):
        community = Community.objects.create(name='Célula Alfa')
        ana = Person.objects.create(name='Ana', community=community)
        bia = Person.objects.create(name='Bia', community=community)
        gathering = _community_gathering(community)

        session, count = services.launch_attendance_session(
            gathering=gathering,
            present_person_ids=[ana.id],
            note='Estudo de Romanos; Bia faltou.',
            confirmed_by_id=42,
        )

        assert count == 1
        assert Attendance.objects.get(person=ana, gathering=gathering).is_present
        # Bia não estava presente → nenhuma linha criada para ela.
        assert not Attendance.objects.filter(person=bia, gathering=gathering).exists()
        assert session.note == 'Estudo de Romanos; Bia faltou.'
        assert session.confirmed_by == 42
        assert session.confirmed_at is not None


@pytest.mark.django_db(transaction=True)
def test_launch_session_creates_visitor(church_a):
    """Visitante (só o nome) vira Person status VISITOR na célula, presente (RN-017)."""
    from apps.communities.models import Community

    with schema_context(church_a.schema_name):
        community = Community.objects.create(name='Célula Beta')
        gathering = _community_gathering(community)

        _, count = services.launch_attendance_session(
            gathering=gathering,
            present_person_ids=[],
            visitor_names=['Maria Visitante', '   '],  # branco é ignorado
            confirmed_by_id=1,
        )

        assert count == 1
        visitor = Person.objects.get(name='Maria Visitante')
        assert visitor.status == Person.Status.VISITOR
        assert visitor.community_id == community.id
        assert Attendance.objects.get(person=visitor, gathering=gathering).is_present


@pytest.mark.django_db(transaction=True)
def test_launch_session_upserts_one_per_gathering(church_a):
    """Relançar a sessão atualiza a MESMA (1 por encontro, RN-016) — não duplica."""
    from apps.communities.models import Community

    with schema_context(church_a.schema_name):
        community = Community.objects.create(name='Célula Gama')
        gathering = _community_gathering(community)

        services.launch_attendance_session(
            gathering=gathering, present_person_ids=[], note='primeira'
        )
        services.launch_attendance_session(
            gathering=gathering, present_person_ids=[], note='corrigida'
        )

        assert AttendanceSession.objects.filter(gathering=gathering).count() == 1
        assert AttendanceSession.objects.get(gathering=gathering).note == 'corrigida'


@pytest.mark.django_db(transaction=True)
def test_cell_pending_days_flags_launched(church_a):
    """`cell_pending_days` lista encontros de Comunidade da célula + `is_launched`."""
    from apps.communities.models import Community

    with schema_context(church_a.schema_name):
        community = Community.objects.create(name='Célula Delta')
        g_launched = _community_gathering(community, date=datetime.date(2026, 6, 3))
        g_pending = _community_gathering(community, date=datetime.date(2026, 6, 10))
        services.launch_attendance_session(
            gathering=g_launched, present_person_ids=[], confirmed_by_id=1
        )

        flags = {g.id: g.is_launched for g in services.cell_pending_days(community)}
        assert flags[g_launched.id] is True
        assert flags[g_pending.id] is False
