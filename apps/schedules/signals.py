"""Signals de Escalas (P-ARQ-06 / Sprint 5 §3.7).

A criação de um `ScheduleConflictApproval` é o evento de segurança "exceção de
conflito aprovada". O `SecurityLog` é emitido AQUI (não no service): assim qualquer
caminho que registre uma aprovação — service, shell, futura API — fica auditado de
forma uniforme. O `AuditLog` da aprovação já é coberto pelos receivers globais de
`AuditLogMixin` em `apps/core/signals.py`.

Conectado em `SchedulesConfig.ready()` com `dispatch_uid` (nunca em models.py).
`user_id` vem de `approved_by_id` (o aprovador competente, TENANT-04); o tenant_id
e o IP são resolvidos dentro de `log_security_event`. Sem PII no payload (TENANT-07).
"""

from apps.core.audit import log_security_event


def on_conflict_approval_created(sender, instance, created, **kwargs):
    """SecurityLog 'schedule_exception_approved' ao registrar a aprovação."""
    if not created:
        return
    log_security_event(
        event_type='schedule_exception_approved',
        user_id=instance.approved_by_id,
        payload={
            'schedule_id': instance.schedule_id,
            'ministry_id': instance.schedule.ministry_id,
        },
    )
