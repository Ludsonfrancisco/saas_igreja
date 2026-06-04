"""Ministério/departamento — model do TENANT (TECH_SPEC §5.5).

Os `coordinators` são `Person` (M2M, OD-019 — vários coordenadores por ministério).
Apagar/anonimizar uma Pessoa-coordenadora só remove o vínculo M2M (o ministério
permanece, RN-007). Pessoas participam via o M2M `Person.ministries` (reverse:
`ministry.members`). O escopo de papel resolve por `coordinators__user_id`.
"""

from django.db import models

from apps.core.models import AuditLogMixin, BaseModel


class Ministry(BaseModel, AuditLogMixin):
    """Ministério ou departamento.

    Herda `AuditLogMixin`: create/update/delete auditados automaticamente (core).
    """

    name = models.CharField(max_length=80)
    # OD-019: M2M (não FK) — vários coordenadores por ministério.
    coordinators = models.ManyToManyField(
        'people.Person',
        blank=True,
        related_name='ministries_led',
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
