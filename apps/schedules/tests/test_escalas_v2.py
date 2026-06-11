"""Escalas v2 — Bloco 1 (backend): escopo do coordenador, janela de pendência
configurável, opt-out por evento e roster com sinalização de conflito.

RF-111..116 / RN-020..023 / OD-031. Tudo no schema do tenant (TENANT-04).
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.gatherings.models import Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person
from apps.schedules import services
from apps.schedules.models import MinistryEventOptOut

GOOD_PASSWORD = 'Senha@123'
JUNE = datetime.date(2026, 6, 14)
JULY = datetime.date(2026, 7, 12)


def _user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _ministry_with_member(name='Louvor', member_name='Ana'):
    ministry = Ministry.objects.create(name=name)
    member = Person.objects.create(name=member_name)
    member.ministries.add(ministry)
    return ministry, member


def _coordinator(ministry, user, name='Coord'):
    coord_person = Person.objects.create(name=name, user_id=user.id)
    ministry.coordinators.add(coord_person)
    return coord_person


def _gathering(date=JUNE, gtype=Gathering.Type.WORSHIP, title='Culto'):
    return Gathering.objects.create(gathering_type=gtype, date=date, title=title)


# --- RN-020: escopo do coordenador -------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_coordinated_ministries_scopes_to_coordinator(church_a):
    coord = _user(church_a, 'coord@a.com', ['leader'])
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        m1, _ = _ministry_with_member(name='Louvor')
        m2, _ = _ministry_with_member(name='Recepcao', member_name='Bia')
        _coordinator(m1, coord)  # coordena só o Louvor

        mine = list(
            services.coordinated_ministries(coord).values_list('name', flat=True)
        )
        assert mine == ['Louvor']

        all_names = set(
            services.coordinated_ministries(pastor).values_list('name', flat=True)
        )
        assert all_names == {'Louvor', 'Recepcao'}


# --- RF-113: roster com sinalização de conflito ------------------------------


@pytest.mark.django_db(transaction=True)
def test_ministry_roster_flags_conflict_and_scheduled_here(church_a):
    with schema_context(church_a.schema_name):
        ministry, ana = _ministry_with_member(member_name='Ana')
        bia = Person.objects.create(name='Bia')
        bia.ministries.add(ministry)
        event = _gathering(title='Culto noite')
        other = _gathering(title='Culto manha')  # mesma data

        # Ana já escalada em OUTRO encontro na mesma data → conflito (cinza).
        services.create_schedule(ministry=ministry, person=ana, gathering=other)
        # Bia já escalada NESTE evento por este ministério.
        services.create_schedule(ministry=ministry, person=bia, gathering=event)

        roster = {
            r['person'].name: r
            for r in services.ministry_roster(ministry=ministry, gathering=event)
        }
        assert roster['Ana']['conflict_elsewhere'] is True
        assert roster['Ana']['scheduled_here'] is False
        assert roster['Bia']['scheduled_here'] is True
        assert roster['Bia']['conflict_elsewhere'] is False


# --- RN-021: conflito é cinza, não trava (escalável via exceção) -------------


@pytest.mark.django_db(transaction=True)
def test_conflict_is_schedulable_via_exception(church_a):
    coord = _user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        ministry, ana = _ministry_with_member(member_name='Ana')
        _coordinator(ministry, coord)
        g1 = _gathering(title='Culto manha')
        g2 = _gathering(title='Culto noite')  # mesma data
        services.create_schedule(ministry=ministry, person=ana, gathering=g1)

        # Sem exceção, criar normal bloqueia (cinza).
        with pytest.raises(ValidationError):
            services.create_schedule(ministry=ministry, person=ana, gathering=g2)

        # Coordenador autoriza a exceção → escala mesmo assim.
        schedule, approval = services.approve_exception(
            actor=coord,
            ministry=ministry,
            person=ana,
            gathering=g2,
            justification='Coordenador autoriza acumulo.',
        )
        assert schedule.pk is not None and approval.pk is not None


# --- RF-114 / RN-022: opt-out por ministério/evento --------------------------


@pytest.mark.django_db(transaction=True)
def test_set_optout_only_by_coordinator_and_unique(church_a):
    coord = _user(church_a, 'coord@a.com', ['leader'])
    other = _user(church_a, 'outro@a.com', ['leader'])  # não coordena
    with schema_context(church_a.schema_name):
        ministry, _ = _ministry_with_member()
        _coordinator(ministry, coord)
        event = _gathering()

        # Quem não coordena o ministério não marca.
        with pytest.raises(ValidationError):
            services.set_optout(ministry=ministry, gathering=event, actor=other)

        # Coordenador marca; remarcar é idempotente (único por par).
        services.set_optout(ministry=ministry, gathering=event, actor=coord)
        services.set_optout(
            ministry=ministry, gathering=event, actor=coord, reason='Sem demanda'
        )
        assert (
            MinistryEventOptOut.objects.filter(
                ministry=ministry, gathering=event
            ).count()
            == 1
        )


@pytest.mark.django_db(transaction=True)
def test_optout_removable_by_pastor(church_a):
    coord = _user(church_a, 'coord@a.com', ['leader'])
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        ministry, _ = _ministry_with_member()
        _coordinator(ministry, coord)
        event = _gathering()
        services.set_optout(ministry=ministry, gathering=event, actor=coord)

        services.remove_optout(ministry=ministry, gathering=event, actor=pastor)
        assert not MinistryEventOptOut.objects.filter(
            ministry=ministry, gathering=event
        ).exists()


# --- RF-116 / RN-023 / OD-031: janela de pendência configurável --------------


def test_is_pending_window_current_and_next_month():
    # Mês corrente sempre na janela.
    assert (
        services.is_pending_window(JUNE, today=datetime.date(2026, 6, 1), open_day=25)
        is True
    )
    # Mês seguinte só a partir do dia configurado.
    assert (
        services.is_pending_window(JULY, today=datetime.date(2026, 6, 14), open_day=25)
        is False
    )
    assert (
        services.is_pending_window(JULY, today=datetime.date(2026, 6, 26), open_day=25)
        is True
    )
    # Configurável: open_day menor antecipa.
    assert (
        services.is_pending_window(JULY, today=datetime.date(2026, 6, 14), open_day=10)
        is True
    )
    # m+2 nunca entra.
    assert (
        services.is_pending_window(
            datetime.date(2026, 8, 3), today=datetime.date(2026, 6, 26), open_day=25
        )
        is False
    )


@pytest.mark.django_db(transaction=True)
def test_active_window_gatherings_respects_open_day(church_a):
    with schema_context(church_a.schema_name):
        june = _gathering(date=JUNE, title='Junho')
        july = _gathering(date=JULY, title='Julho')

        before = services.active_window_gatherings(
            today=datetime.date(2026, 6, 14), open_day=25
        )
        assert set(before.values_list('pk', flat=True)) == {june.pk}

        after = services.active_window_gatherings(
            today=datetime.date(2026, 6, 26), open_day=25
        )
        assert set(after.values_list('pk', flat=True)) == {june.pk, july.pk}


# --- RF-115: pendências do coordenador ---------------------------------------


@pytest.mark.django_db(transaction=True)
def test_pending_events_excludes_scheduled_and_optout(church_a):
    coord = _user(church_a, 'coord@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        ministry, member = _ministry_with_member()
        _coordinator(ministry, coord)
        e_pending = _gathering(date=JUNE, title='Pendente')
        e_scheduled = _gathering(date=JUNE, title='Escalado')
        e_optout = _gathering(date=JUNE, title='OptOut')

        services.create_schedule(
            ministry=ministry, person=member, gathering=e_scheduled
        )
        services.set_optout(ministry=ministry, gathering=e_optout, actor=coord)

        pending = services.pending_events_for_user(
            user=coord, open_day=25, today=datetime.date(2026, 6, 14)
        )
        assert set(pending.values_list('pk', flat=True)) == {e_pending.pk}
