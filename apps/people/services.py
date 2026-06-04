"""Service layer de Pessoas — regras LGPD e de plano (RF-030 / RN-005..007 / OPS-04/05).

Camada fina (P-ARQ-04) entre as views/CRUD e o ORM. Concentra as regras que NÃO
podem viver só no ModelForm — porque a importação CSV (Frente 5) não passa por form:

- CONSENTIMENTO (OPS-05 / OD-018 / RN-005): se `email` ou `phone` está preenchido,
  `consent_given_at` é obrigatório. Barreira efetiva aqui; o form espelha p/ UX.
- LIMITE DE PLANO (OPS-04): `create_person` recusa quando a igreja atinge
  `Plan.PLAN_LIMITS[church.plan]['max_persons']` (0 = ilimitado). Conta só o
  cadastro ATIVO (não-anonimizado).
- LGPD (RN-005..007): `anonymize_person` (soft delete imediato + substitui PII +
  `anonymized_at`; SecurityLog `person_anonymized`) e `export_person_data`
  (JSON+CSV; SecurityLog `person_exported`).

AUDITORIA: Person herda `AuditLogMixin` → create/update/delete já geram AuditLog
automático (core signals, ator via thread-local do `AuditContextMiddleware`). Por
isso os services NÃO recebem `actor` nem chamam `record_audit` nessas ações (a
lição da Frente 5: nada de parâmetro morto). As ações LGPD especiais adicionam
`SecurityLog`; o `export` ainda faz um `record_audit('export')` explícito porque
não há escrita no banco que dispare o signal.
"""

import csv
import io
import json

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.audit import log_security_event, record_audit
from apps.people.models import Person
from apps.tenants.models import Plan

# Campos que create/update aceitam (whitelist explícita — nunca **fields cego).
_EDITABLE_FIELDS = (
    'name',
    'email',
    'phone',
    'birth_date',
    'status',
    'community',
    'consent_given_at',
    'notes',
    'user_id',
)
_UNSET = object()


def _require_consent(email, phone, consent_given_at):
    """RN-005: PII de contato (email/telefone) exige consentimento registrado."""
    if (email or phone) and consent_given_at is None:
        raise ValidationError(
            'Consentimento (LGPD) e obrigatorio quando email ou telefone e informado.'
        )


def _enforce_plan_limit(church):
    """OPS-04: recusa se a igreja atingiu o limite de pessoas do plano (0=ilimitado)."""
    max_persons = Plan.PLAN_LIMITS.get(church.plan, {}).get('max_persons', 0)
    if not max_persons:
        return
    active = Person.objects.filter(anonymized_at__isnull=True).count()
    if active >= max_persons:
        raise ValidationError(
            f'Limite do plano atingido: {max_persons} pessoas. '
            'Faca upgrade para cadastrar mais.'
        )


def create_person(
    *,
    church,
    name,
    status=Person.Status.VISITOR,
    email=None,
    phone=None,
    birth_date=None,
    community=None,
    ministries=None,
    consent_given_at=None,
    notes='',
    user_id=None,
):
    """Cria uma Pessoa aplicando consentimento (RN-005) e limite de plano (OPS-04).

    `user_id` (opcional) liga o Person a um User-staff (líder/coordenador) por id
    (TENANT-04, não-FK). AuditLog('create') é automático. Retorna a Person criada.
    """
    _require_consent(email, phone, consent_given_at)
    _enforce_plan_limit(church)

    person = Person.objects.create(
        name=name,
        status=status,
        email=email,
        phone=phone,
        birth_date=birth_date,
        community=community,
        consent_given_at=consent_given_at,
        notes=notes,
        user_id=user_id,
    )
    if ministries:
        person.ministries.set(ministries)
    return person


def update_person(*, person, ministries=_UNSET, **fields):
    """Atualiza campos de uma Pessoa, revalidando o consentimento (RN-005).

    Aceita apenas os campos de `_EDITABLE_FIELDS`. AuditLog('update') automático.
    """
    unknown = set(fields) - set(_EDITABLE_FIELDS)
    if unknown:
        raise ValidationError(f'Campos invalidos: {sorted(unknown)}.')

    for key, value in fields.items():
        setattr(person, key, value)

    _require_consent(person.email, person.phone, person.consent_given_at)
    person.save()

    if ministries is not _UNSET:
        person.ministries.set(ministries or [])
    return person


def change_status(*, person, status):
    """Muda apenas o `status` (TextChoices). AuditLog('update') automático."""
    if status not in Person.Status.values:
        raise ValidationError('Status invalido.')
    person.status = status
    person.save(update_fields=['status', 'updated_at'])
    return person


def anonymize_person(*, person):
    """Anonimiza (soft delete LGPD): substitui PII e marca `anonymized_at` (RN-005/6/7).

    Irreversível. Idempotente (já anonimizada → no-op). Desvincula comunidade e
    ministérios e marca `INACTIVE`. O purge físico (Frente 3, Celery Beat) remove a
    linha após 30 dias — só aí as FKs de outros models para esta Person viram NULL
    (SET_NULL). AuditLog('update') é automático; emite SecurityLog
    `person_anonymized` (payload sem PII — apenas o id).
    """
    if person.anonymized_at is not None:
        return person

    person.name = f'Pessoa anonimizada #{person.pk}'
    person.email = None
    person.phone = None
    person.birth_date = None
    person.notes = ''
    person.consent_given_at = None
    person.community = None
    person.status = Person.Status.INACTIVE
    person.anonymized_at = timezone.now()
    person.save()
    person.ministries.clear()

    log_security_event(
        event_type='person_anonymized',
        payload={'person_id': person.pk},
    )
    return person


def export_person_data(*, person):
    """Exporta os dados da Pessoa em JSON e CSV (RN-005 / direito de acesso LGPD).

    Toda exportação gera AuditLog('export') + SecurityLog `person_exported`
    (payload sem PII). Como não há escrita no banco, o `record_audit` é explícito
    (o signal de auditoria só cobre save/delete). Retorna
    `{'data': dict, 'json': str, 'csv': str}`.
    """
    data = {
        'id': person.pk,
        'name': person.name,
        'email': person.email,
        'phone': person.phone,
        'birth_date': person.birth_date.isoformat() if person.birth_date else None,
        'status': person.status,
        'community': person.community.name if person.community else None,
        'ministries': list(person.ministries.values_list('name', flat=True)),
        'consent_given_at': (
            person.consent_given_at.isoformat() if person.consent_given_at else None
        ),
        'notes': person.notes,
        'created_at': person.created_at.isoformat(),
    }

    json_payload = json.dumps(data, ensure_ascii=False, indent=2)

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(data.keys())
    writer.writerow(
        [
            (
                '; '.join(value)
                if isinstance(value, list)
                else ('' if value is None else value)
            )
            for value in data.values()
        ]
    )
    csv_payload = csv_buffer.getvalue()

    record_audit(action='export', instance=person)
    log_security_event(
        event_type='person_exported',
        payload={'person_id': person.pk},
    )
    return {'data': data, 'json': json_payload, 'csv': csv_payload}
