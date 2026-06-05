"""Sprint 3 / Frente 2 (Bloco 1) — services de Pessoa: LGPD, plano e auditoria.

Cobre os testes mínimos da Sprint 3 ligados ao service layer:
`test_person_create_requires_consent_*`, `test_person_create_respects_plan_max_persons`,
`test_anonymize_*`, `test_export_*`, `test_person_actions_audited` (create/update).

Person é model de TENANT — os testes rodam dentro do schema do tenant A
(`in_tenant_a`), onde também vivem AuditLog/SecurityLog. `transaction=True` porque
criar Church dispara DDL.
"""

import csv
import io
import json

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import AuditLog, SecurityLog
from apps.people import services
from apps.people.models import Person
from apps.tenants.models import Plan

# --- Consentimento (RN-005 / OPS-05) ----------------------------------------


@pytest.mark.django_db(transaction=True)
def test_person_create_without_contact_does_not_require_consent(in_tenant_a):
    person = services.create_person(church=in_tenant_a, name='Sem Contato')
    assert person.pk is not None
    assert person.consent_given_at is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'field,value', [('email', 'a@a.com'), ('phone', '11999990000')]
)
def test_person_create_requires_consent_when_email_or_phone(in_tenant_a, field, value):
    """Email OU telefone preenchido sem consent -> ValidationError, nada criado."""
    with pytest.raises(ValidationError):
        services.create_person(church=in_tenant_a, name='Com Contato', **{field: value})
    assert Person.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_person_create_with_consent_and_contact_ok(in_tenant_a):
    person = services.create_person(
        church=in_tenant_a,
        name='Maria',
        email='m@a.com',
        consent_given_at=timezone.now(),
    )
    assert person.email == 'm@a.com'


@pytest.mark.django_db(transaction=True)
def test_update_person_requires_consent_when_adding_contact(in_tenant_a):
    person = services.create_person(church=in_tenant_a, name='Joao')
    with pytest.raises(ValidationError):
        services.update_person(person=person, phone='11988887777')


# --- Limite de plano (OPS-04) -----------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_person_create_respects_plan_max_persons(in_tenant_a, monkeypatch):
    """Atingido `max_persons` do plano -> recusa. (limite reduzido p/ 2 no teste)."""
    monkeypatch.setitem(Plan.PLAN_LIMITS['free'], 'max_persons', 2)

    services.create_person(church=in_tenant_a, name='P1')
    services.create_person(church=in_tenant_a, name='P2')
    with pytest.raises(ValidationError):
        services.create_person(church=in_tenant_a, name='P3')

    assert Person.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_anonymized_persons_do_not_count_against_plan_limit(in_tenant_a, monkeypatch):
    """Cadastro anonimizado não ocupa vaga do plano (conta só o ativo)."""
    monkeypatch.setitem(Plan.PLAN_LIMITS['free'], 'max_persons', 1)
    p1 = services.create_person(church=in_tenant_a, name='P1')
    services.anonymize_person(person=p1)
    # p1 anonimizada não conta -> dá para criar outra.
    p2 = services.create_person(church=in_tenant_a, name='P2')
    assert p2.pk is not None


# --- Anonimização (RN-005/006/007) ------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_anonymize_person_replaces_pii_and_sets_inactive(in_tenant_a):
    person = services.create_person(
        church=in_tenant_a,
        name='Joao Silva',
        email='j@a.com',
        phone='11977776666',
        consent_given_at=timezone.now(),
    )
    services.anonymize_person(person=person)
    person.refresh_from_db()

    assert person.email is None
    assert person.phone is None
    assert person.consent_given_at is None
    assert person.community is None
    assert person.status == Person.Status.INACTIVE
    assert person.anonymized_at is not None
    assert 'Joao' not in person.name


@pytest.mark.django_db(transaction=True)
def test_anonymize_person_is_idempotent(in_tenant_a):
    person = services.create_person(church=in_tenant_a, name='Ze')
    services.anonymize_person(person=person)
    person.refresh_from_db()
    first_ts = person.anonymized_at

    services.anonymize_person(person=person)
    person.refresh_from_db()

    assert person.anonymized_at == first_ts
    assert SecurityLog.objects.filter(event_type='person_anonymized').count() == 1


@pytest.mark.django_db(transaction=True)
def test_anonymize_person_audited(in_tenant_a):
    person = services.create_person(church=in_tenant_a, name='Carla')
    services.anonymize_person(person=person)

    log = SecurityLog.objects.get(event_type='person_anonymized')
    assert log.payload['person_id'] == person.pk
    assert 'Carla' not in json.dumps(log.payload)  # sem PII no payload


# --- Exportação (RN-005, direito de acesso) ---------------------------------


@pytest.mark.django_db(transaction=True)
def test_export_person_data_returns_json_and_csv(in_tenant_a):
    person = services.create_person(
        church=in_tenant_a,
        name='Bia',
        email='b@a.com',
        consent_given_at=timezone.now(),
    )
    result = services.export_person_data(person=person)

    parsed = json.loads(result['json'])
    assert parsed['name'] == 'Bia'
    assert parsed['email'] == 'b@a.com'

    rows = list(csv.reader(io.StringIO(result['csv'])))
    assert rows[0] == list(parsed.keys())  # header
    assert 'Bia' in rows[1]


@pytest.mark.django_db(transaction=True)
def test_export_person_data_includes_attendance(in_tenant_a):
    """Direito de acesso LGPD: export traz a frequência (não só o registro)."""
    import datetime

    from apps.gatherings.models import Attendance, Gathering

    person = services.create_person(church=in_tenant_a, name='Léo')
    gathering = Gathering.objects.create(
        gathering_type=Gathering.Type.WORSHIP,
        title='Culto',
        date=datetime.date(2026, 6, 10),
    )
    Attendance.objects.create(gathering=gathering, person=person, is_present=True)

    result = services.export_person_data(person=person)
    parsed = json.loads(result['json'])

    assert len(parsed['attendances']) == 1
    assert '2026-06-10' in parsed['attendances'][0]
    assert 'presente' in parsed['attendances'][0]
    # CSV achata a lista com '; ' (frase legível, sem quebrar o writer).
    rows = list(csv.reader(io.StringIO(result['csv'])))
    assert rows[0] == list(parsed.keys())


@pytest.mark.django_db(transaction=True)
def test_export_person_data_audited(in_tenant_a):
    person = services.create_person(church=in_tenant_a, name='Rui')
    services.export_person_data(person=person)

    assert AuditLog.objects.filter(
        model_name='Person', action='export', object_id=str(person.pk)
    ).exists()
    assert SecurityLog.objects.filter(
        event_type='person_exported', payload__person_id=person.pk
    ).exists()


# --- Auditoria automática (AuditLogMixin) e change_status -------------------


@pytest.mark.django_db(transaction=True)
def test_person_actions_audited(in_tenant_a):
    """create e update geram AuditLog automático (via AuditLogMixin/core signals)."""
    person = services.create_person(church=in_tenant_a, name='Ana')
    assert AuditLog.objects.filter(
        model_name='Person', action='create', object_id=str(person.pk)
    ).exists()

    services.update_person(person=person, name='Ana Maria')
    assert AuditLog.objects.filter(
        model_name='Person', action='update', object_id=str(person.pk)
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_change_status(in_tenant_a):
    person = services.create_person(church=in_tenant_a, name='Lia')
    services.change_status(person=person, status=Person.Status.MEMBER)
    person.refresh_from_db()
    assert person.status == Person.Status.MEMBER

    with pytest.raises(ValidationError):
        services.change_status(person=person, status='bogus')


@pytest.mark.django_db(transaction=True)
def test_create_and_update_person_with_ministries(in_tenant_a):
    from apps.ministries.models import Ministry

    louvor = Ministry.objects.create(name='Louvor')
    midia = Ministry.objects.create(name='Midia')

    person = services.create_person(church=in_tenant_a, name='Ana', ministries=[louvor])
    assert list(person.ministries.all()) == [louvor]

    services.update_person(person=person, ministries=[louvor, midia])
    assert person.ministries.count() == 2


@pytest.mark.django_db(transaction=True)
def test_update_person_rejects_unknown_field(in_tenant_a):
    person = services.create_person(church=in_tenant_a, name='Rui')
    with pytest.raises(ValidationError):
        services.update_person(person=person, bogus='x')


@pytest.mark.django_db(transaction=True)
def test_create_person_unlimited_plan_skips_limit(in_tenant_a, monkeypatch):
    """Plano com max_persons=0 (ilimitado) não bloqueia novos cadastros."""
    monkeypatch.setitem(Plan.PLAN_LIMITS['free'], 'max_persons', 0)
    for i in range(3):
        services.create_person(church=in_tenant_a, name=f'P{i}')
    assert Person.objects.count() == 3
