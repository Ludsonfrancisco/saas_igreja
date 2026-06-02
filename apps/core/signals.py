"""Signals de auditoria automatica (P-ARQ-06).

Receivers globais de `post_save`/`post_delete` que, para qualquer instancia de um
model que herde de `AuditLogMixin`, gravam um AuditLog via `record_audit`:

- post_save com `created=True`  -> action='create'
- post_save com `created=False` -> action='update'
- post_delete                   -> action='delete'

Filtro: so auditamos subclasses de `AuditLogMixin`. AuditLog/SecurityLog NAO
herdam do mixin, entao nunca disparam auditoria de si mesmos (sem recursao). O
user_id/IP do ator vem do thread-local (`AuditContextMiddleware`); o tenant_id
vem de `connection.schema_name` dentro de `record_audit`.

P-ARQ-06: estes receivers sao CONECTADOS em `CoreConfig.ready()` (import deste
modulo), nunca em models.py.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.core.audit import record_audit
from apps.core.models import AuditLogMixin


@receiver(post_save)
def audit_on_save(sender, instance, created, **kwargs):
    """Audita create/update de qualquer subclasse de AuditLogMixin."""
    if not isinstance(instance, AuditLogMixin):
        return
    record_audit(action='create' if created else 'update', instance=instance)


@receiver(post_delete)
def audit_on_delete(sender, instance, **kwargs):
    """Audita delete de qualquer subclasse de AuditLogMixin."""
    if not isinstance(instance, AuditLogMixin):
        return
    record_audit(action='delete', instance=instance)
