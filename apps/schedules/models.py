"""Escalas de voluntários — models do TENANT (TECH_SPEC §5.7 / Sprint 5).

`Schedule` aloca uma `Person` (voluntário) num `Ministry` para um `Gathering`
(encontro). O bloqueio de conflito (mesma pessoa em dois encontros na mesma data)
vive no service; a exceção autorizada é registrada em `ScheduleConflictApproval`.

TENANT-04: nenhuma FK para User. O aprovador é guardado por `approved_by_id`
(user_id). `Schedule.person` é `SET_NULL` (RN-007 / OD-020): o purge físico da
Pessoa preserva o registro histórico da escala.
"""

from django.db import models

from apps.core.models import AuditLogMixin, BaseModel


class Schedule(BaseModel, AuditLogMixin):
    """Escala de um voluntário (`person`) num `ministry` para um `gathering`.

    Herda `AuditLogMixin` (create/update/delete auditados pelos signals do core).
    `person` é `on_delete=SET_NULL` (RN-007 / OD-020) — por isso nullable.
    """

    ministry = models.ForeignKey(
        'ministries.Ministry',
        on_delete=models.CASCADE,
        related_name='schedules',
    )
    person = models.ForeignKey(
        'people.Person',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedules',
    )
    gathering = models.ForeignKey(
        'gatherings.Gathering',
        on_delete=models.CASCADE,
        related_name='schedules',
    )
    role = models.CharField(max_length=60, blank=True, default='')
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ('-gathering__date', 'ministry__name')

    def __str__(self):
        who = self.person.name if self.person else '(removida)'
        return f'{who} — {self.ministry.name} @ {self.gathering}'


class ScheduleConflictApproval(BaseModel, AuditLogMixin):
    """Aprovação explícita de uma exceção de conflito de escala (§3.7).

    Criada por `services.approve_exception` apenas pelo Pastor ou pelo Coordenador
    competente (coordenador do `schedule.ministry`). `approved_by_id` é o `user_id`
    do aprovador (TENANT-04). Herda `AuditLogMixin` (AuditLog automático na criação)
    e o service emite SecurityLog `schedule_exception_approved`.
    """

    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='conflict_approvals',
    )
    approved_by_id = models.IntegerField(help_text='User.id do aprovador competente')
    justification = models.TextField()
    approved_at = models.DateTimeField()

    def __str__(self):
        return f'Excecao aprovada: schedule #{self.schedule_id}'


class MinistryEventOptOut(BaseModel, AuditLogMixin):
    """Opt-out de um ministério num evento (Escalas v2 / RF-114, RN-022).

    "Não atuaremos nesse evento": o coordenador marca que o `ministry` **não vai
    atuar** no `gathering` — some a pendência daquele par e o ministério deixa de
    aparecer como escalável no modal. Único por `(ministry, gathering)`.

    `marked_by_id` é o `user_id` do coordenador (TENANT-04, sem FK para User).
    Herda `AuditLogMixin` (1 AuditLog por marcação, leve). Reversível (delete).
    """

    ministry = models.ForeignKey(
        'ministries.Ministry',
        on_delete=models.CASCADE,
        related_name='event_optouts',
    )
    gathering = models.ForeignKey(
        'gatherings.Gathering',
        on_delete=models.CASCADE,
        related_name='ministry_optouts',
    )
    marked_by_id = models.IntegerField(help_text='User.id do coordenador que marcou')
    reason = models.CharField(max_length=120, blank=True, default='')

    class Meta:
        unique_together = (('ministry', 'gathering'),)
        ordering = ('-gathering__date',)

    def __str__(self):
        return f'{self.ministry.name} nao atua em {self.gathering}'
