"""Comunidade (célula/grupo) — model do TENANT (TECH_SPEC §5.5).

Só faz sentido quando `Church.has_communities=True` (igreja em células). O `leader`
é uma `Person` (FK `SET_NULL`: anonimizar/remover a pessoa não apaga a comunidade,
RN-007). Pessoas vinculam-se via `Person.community` (reverse: `community.members`).
"""

from django.db import models

from apps.core.models import BaseModel


class Community(BaseModel):
    """Comunidade. Ativa apenas se `Church.has_communities=True`."""

    name = models.CharField(max_length=80)
    leader = models.ForeignKey(
        'people.Person',
        on_delete=models.SET_NULL,
        null=True,
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
