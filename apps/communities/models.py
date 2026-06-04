"""Comunidade (célula/grupo) — model do TENANT (TECH_SPEC §5.5).

Só faz sentido quando `Church.has_communities=True` (igreja em células). Os
`leaders` são `Person` (M2M, OD-019 — uma comunidade pode ter VÁRIOS líderes:
casal de líderes, líder + auxiliar). Pessoas-membros vinculam-se via
`Person.community` (reverse: `community.members`). O escopo de papel resolve por
`Community.leaders` → `Person.user_id` (lookup `leaders__user_id`).
"""

from django.db import models

from apps.core.models import AuditLogMixin, BaseModel


class Community(BaseModel, AuditLogMixin):
    """Comunidade. Ativa apenas se `Church.has_communities=True`.

    Herda `AuditLogMixin`: create/update/delete auditados automaticamente (core).
    """

    name = models.CharField(max_length=80)
    # OD-019: M2M (não FK) — vários líderes por comunidade. Apagar/anonimizar uma
    # Person-líder só remove o vínculo M2M (a comunidade permanece, RN-007).
    leaders = models.ManyToManyField(
        'people.Person',
        blank=True,
        related_name='communities_led',
    )
    # null=True conforme TECH_SPEC §5.5 (dia/horário de reunião opcionais). DJ001
    # suprimido: fiel à spec; campo não-PII, sem impacto de convenção vazia.
    meeting_day = models.CharField(max_length=15, null=True, blank=True)  # noqa: DJ001
    meeting_time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
