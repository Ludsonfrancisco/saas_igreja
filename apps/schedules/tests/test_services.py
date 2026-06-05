"""Sprint 5 / Frente 1 — service de Escalas (vínculo + bloqueio de conflito, §3.7).

Regra de negócio pura dentro do schema do tenant. Person/Ministry/Gathering/Schedule
vivem no tenant (TENANT-04).
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.core.models import AuditLog, SecurityLog
from apps.gatherings.models import Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person
from apps.schedules import services
from apps.schedules.models import ScheduleConflictApproval

DATE = datetime.date(2026, 6, 14)
GOOD_PASSWORD = 'Senha@123'


def _ministry_with_member(name='Louvor', member_name='Ana'):
    ministry = Ministry.objects.create(name=name)
    member = Person.objects.create(name=member_name)
    member.ministries.add(ministry)
    return ministry, member


def _gathering(date=DATE, gtype=Gathering.Type.WORSHIP, title='Culto'):
    return Gathering.objects.create(gathering_type=gtype, date=date, title=title)


def _user(church, email, roles):
    # User é model público (TENANT-04) — criado fora do schema do tenant.
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _coordinator(ministry, user, name='Coord'):
    """Vincula `user` como Coordenador competente de `ministry` (Person + M2M)."""
    coord_person = Person.objects.create(name=name, user_id=user.id)
    ministry.coordinators.add(coord_person)
    return coord_person


def _conflict_setup(coord_user=None):
    """Monta um conflito: `member` já escalado em `g1` na DATE; `g2` (mesma data,
    outro encontro) será o conflito que a exceção precisa autorizar."""
    ministry, member = _ministry_with_member()
    if coord_user is not None:
        _coordinator(ministry, coord_user)
    g1 = _gathering(title='Culto manha')
    g2 = _gathering(title='Culto noite')
    services.create_schedule(ministry=ministry, person=member, gathering=g1)
    return ministry, member, g2


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


# --- aprovação de exceção de conflito (Frente 2, §3.7) -----------------------


@pytest.mark.django_db(transaction=True)
def test_schedule_exception_requires_competent_coordinator(church_a):
    """Só Pastor ou Coordenador competente aprova; outro líder é barrado."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    coord = _user(church_a, 'coord@a.com', ['leader'])
    other_leader = _user(church_a, 'outro@a.com', ['leader'])  # não coordena
    with schema_context(church_a.schema_name):
        ministry, member, g2 = _conflict_setup(coord_user=coord)

        # Líder que NÃO coordena o ministério → barrado.
        with pytest.raises(ValidationError):
            services.approve_exception(
                actor=other_leader,
                ministry=ministry,
                person=member,
                gathering=g2,
                justification='Faltou voluntario.',
            )

        # Coordenador competente → aprova.
        schedule, approval = services.approve_exception(
            actor=coord,
            ministry=ministry,
            person=member,
            gathering=g2,
            justification='Coordenador autoriza acumulo.',
        )
        assert schedule.pk is not None
        assert approval.approved_by_id == coord.id

        # Pastor aprova em qualquer ministério (novo conflito no mesmo dia).
        g3 = _gathering(title='Culto tarde')
        schedule_p, _ = services.approve_exception(
            actor=pastor,
            ministry=ministry,
            person=member,
            gathering=g3,
            justification='Pastor autoriza.',
        )
        assert schedule_p.pk is not None


@pytest.mark.django_db(transaction=True)
def test_schedule_exception_requires_justification(church_a):
    """Justificativa vazia é rejeitada (RN-014 — toda exceção é justificada)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        ministry, member, g2 = _conflict_setup()
        with pytest.raises(ValidationError):
            services.approve_exception(
                actor=pastor,
                ministry=ministry,
                person=member,
                gathering=g2,
                justification='   ',
            )


@pytest.mark.django_db(transaction=True)
def test_schedule_exception_rejected_without_real_conflict(church_a):
    """Sem conflito real, deve usar a criação normal — exceção é rejeitada."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        ministry, member = _ministry_with_member()
        gathering = _gathering()  # nenhuma escala prévia → sem conflito
        with pytest.raises(ValidationError):
            services.approve_exception(
                actor=pastor,
                ministry=ministry,
                person=member,
                gathering=gathering,
                justification='Sem conflito aqui.',
            )


@pytest.mark.django_db(transaction=True)
def test_schedule_exception_creates_approval_and_audits(church_a):
    """Cria Schedule + ScheduleConflictApproval; criação da aprovação é auditada."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        ministry, member, g2 = _conflict_setup()
        schedule, approval = services.approve_exception(
            actor=pastor,
            ministry=ministry,
            person=member,
            gathering=g2,
            justification='Acumulo aprovado pelo pastor.',
        )

        assert ScheduleConflictApproval.objects.filter(schedule=schedule).count() == 1
        assert approval.justification == 'Acumulo aprovado pelo pastor.'

        # AuditLog automático (AuditLogMixin) na criação da aprovação.
        assert AuditLog.objects.filter(
            action='create',
            model_name='ScheduleConflictApproval',
            object_id=str(approval.pk),
        ).exists()


@pytest.mark.django_db(transaction=True)
def test_schedule_exception_security_logged(church_a):
    """Emite SecurityLog `schedule_exception_approved` com actor e schedule."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        ministry, member, g2 = _conflict_setup()
        schedule, _ = services.approve_exception(
            actor=pastor,
            ministry=ministry,
            person=member,
            gathering=g2,
            justification='Justificativa.',
        )

        log = SecurityLog.objects.filter(
            event_type='schedule_exception_approved', user_id=pastor.id
        ).first()
        assert log is not None
        assert log.payload['schedule_id'] == schedule.pk
        assert log.payload['ministry_id'] == ministry.pk
