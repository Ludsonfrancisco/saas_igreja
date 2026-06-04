"""Tasks Celery de Pessoas (Frente 2 / Bloco 3).

`purge_anonymized_persons`: purge físico semanal do soft delete LGPD (RN-006).
Roda via Celery Beat (schedule em settings). Itera TODOS os schemas de tenant
(o Person só existe no tenant — o public é excluído) e remove as pessoas
anonimizadas há mais de 30 dias.

O `delete()` dispara `post_delete` → AuditLog('delete') automático (AuditLogMixin)
e zera (SET_NULL) as FKs que apontam para a pessoa (community.leader,
ministry.coordinator, etc.) — preservando o restante da trilha (RN-007).
"""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context

_PURGE_AFTER = timedelta(days=30)


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
