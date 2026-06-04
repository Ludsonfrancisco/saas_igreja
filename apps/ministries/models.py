"""Ministério/departamento — model do TENANT (TECH_SPEC §5.5).

O `coordinator` é uma `Person` (FK `SET_NULL`: anonimizar/remover a pessoa não
apaga o ministério, RN-007). Pessoas participam via o M2M `Person.ministries`
(reverse: `ministry.members`).
"""

from django.db import models

from apps.core.models import AuditLogMixin, BaseModel


class Ministry(BaseModel, AuditLogMixin):
    """Ministério ou departamento.

    Herda `AuditLogMixin`: create/update/delete auditados automaticamente (core).
    """

    name = models.CharField(max_length=80)
    coordinator = models.ForeignKey(
        'people.Person',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ministries_led',
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
