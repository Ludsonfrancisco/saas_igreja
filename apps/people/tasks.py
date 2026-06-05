"""Tasks Celery de Pessoas (Frente 2 / Bloco 3).

`purge_anonymized_persons`: purge físico semanal do soft delete LGPD (RN-006).
Roda via Celery Beat (schedule em settings). Itera TODOS os schemas de tenant
(o Person só existe no tenant — o public é excluído) e remove as pessoas
anonimizadas há mais de 30 dias.

O `delete()` dispara `post_delete` → AuditLog('delete') automático (AuditLogMixin)
e zera (SET_NULL) as FKs que apontam para a pessoa (community.leader,
ministry.coordinator, etc.) — preservando o restante da trilha (RN-007).
"""

import csv
import io
from datetime import timedelta

from celery import shared_task
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context

_PURGE_AFTER = timedelta(days=30)
_CONSENT_TRUTHY = {'sim', 'yes', 'true', '1', 's', 'y'}


@shared_task
def purge_anonymized_persons():
    """Remove Person anonimizada há > 30 dias em todos os tenants. Retorna o total."""
    from apps.people.models import Person
    from apps.tenants.models import Church

    cutoff = timezone.now() - _PURGE_AFTER
    public = get_public_schema_name()
    total = 0
    for church in Church.objects.exclude(schema_name=public):
        with schema_context(church.schema_name):
            stale = Person.objects.filter(
                anonymized_at__isnull=False, anonymized_at__lte=cutoff
            )
            count = stale.count()
            stale.delete()
            total += count
    return total


@shared_task
def import_persons_csv(church_schema, content, import_id):
    """Importa pessoas de um CSV (RF-033). Roda no schema do tenant.

    **Idempotente por `import_id`**: se o lote já foi importado, é no-op (re-rodar
    não duplica). Colunas esperadas: `name` (obrigatório), `email`, `phone`,
    `status`, `consent`. Consentimento (OPS-05/RN-005): linha com email/telefone
    SEM `consent` afirmativo é pulada e reportada (não cria). Respeita o limite de
    plano (OPS-04) via `create_person`. Retorna um resumo `{status, created, errors}`.
    """
    from apps.people.models import Person
    from apps.people.services import create_person
    from apps.tenants.models import Church

    with schema_context(church_schema):
        if Person.objects.filter(import_id=import_id).exists():
            return {'status': 'already_imported', 'created': 0, 'errors': []}

        church = Church.objects.get(schema_name=church_schema)
        created = 0
        errors = []
        reader = csv.DictReader(io.StringIO(content))
        # start=2: a linha 1 do arquivo é o cabeçalho.
        for line, row in enumerate(reader, start=2):
            name = (row.get('name') or '').strip()
            if not name:
                errors.append({'row': line, 'error': 'nome obrigatorio'})
                continue
            email = (row.get('email') or '').strip() or None
            phone = (row.get('phone') or '').strip() or None
            consent = (row.get('consent') or '').strip().lower() in _CONSENT_TRUTHY
            status = (row.get('status') or '').strip()
            if status not in Person.Status.values:
                status = Person.Status.VISITOR
            try:
                create_person(
                    church=church,
                    name=name,
                    email=email,
                    phone=phone,
                    status=status,
                    consent_given_at=timezone.now() if consent else None,
                    import_id=import_id,
                )
                created += 1
            except ValidationError as exc:
                errors.append({'row': line, 'error': exc.messages[0]})
        return {'status': 'done', 'created': created, 'errors': errors}
