"""Encontro (culto, reunião de comunidade, evento, reunião) — model do TENANT.

TECH_SPEC §5.6 / ACCESS_MATRIX §3.6 (Sprint 4). Vive no schema do tenant; não
referencia User/Church por FK (TENANT-04). O criador é guardado em `created_by`
(`user_id` do User público), não FK — habilita a trava "editar pelo criador" da
§3.6 (Líder/Coordenador editam o que criaram, além do escopo por comunidade).

`community` (FK `SET_NULL`) só é preenchida em encontros do tipo COMMUNITY; os
demais tipos não têm comunidade. A presença (`Attendance`) chega na Frente 2.
"""

from django.db import models

from apps.core.models import AuditLogMixin, BaseModel


class Gathering(BaseModel, AuditLogMixin):
    """Encontro da igreja. Herda `AuditLogMixin` (create/update/delete auditados).

    Ordem das bases `(BaseModel, AuditLogMixin)` é deliberada: o `isinstance` dos
    receivers de auditoria continua valendo (mixin no MRO). Aqui sobrescrevemos a
    ordenação para `-date` (encontros mais recentes primeiro).
    """

    class Type(models.TextChoices):
        WORSHIP = 'worship', 'Culto'
        COMMUNITY = 'community', 'Reuniao de Comunidade'
        EVENT = 'event', 'Evento'
        MEETING = 'meeting', 'Reuniao'

    gathering_type = models.CharField(
        max_length=12, choices=Type.choices, db_index=True
    )
    # null=True (TECH_SPEC §5.6): título é opcional (um culto semanal pode não ter).
    title = models.CharField(max_length=120, null=True, blank=True)  # noqa: DJ001
    date = models.DateField(db_index=True)
    # Só encontros COMMUNITY têm comunidade. SET_NULL: anonimizar/excluir a
    # comunidade preserva o encontro histórico (RN-007).
    community = models.ForeignKey(
        'communities.Community',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gatherings',
    )
    description = models.TextField(blank=True, default='')
    # user_id do criador (TENANT-04: id do User público, NÃO FK). Habilita a trava
    # "editar pelo criador" da §3.6. NULL para encontros legados/seed.
    created_by = models.IntegerField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ('-date', '-created_at')

    def __str__(self):
        return self.title or f'{self.get_gathering_type_display()} {self.date}'


class Attendance(BaseModel):
    """Presença de uma Pessoa em um Encontro (RF-040 / RN-009 / §5.6).

    `unique_together (person, gathering)` + `update_or_create` (RN-009): marcar duas
    vezes nunca duplica. NÃO herda `AuditLogMixin` (OD-020): presença é operação de
    alta frequência (marcação em lote) — auditar cada linha geraria ruído.

    `person` é `on_delete=SET_NULL` (RN-007 / OD-020): o purge físico da Pessoa
    preserva a presença histórica do encontro (a contagem fica; a identidade some).
    Por isso `person` é nullable. `gathering` é CASCADE (apagar o encontro apaga a
    sua lista de presença).
    """

    person = models.ForeignKey(
        'people.Person',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendances',
    )
    gathering = models.ForeignKey(
        'Gathering',
        on_delete=models.CASCADE,
        related_name='attendances',
    )
    is_present = models.BooleanField(default=True)

    class Meta:
        unique_together = ('person', 'gathering')
        ordering = ('-created_at',)

    def __str__(self):
        who = self.person.name if self.person else '(anonimizada)'
        return f'{who} @ {self.gathering}'
