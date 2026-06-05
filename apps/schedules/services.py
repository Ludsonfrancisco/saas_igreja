"""Service layer de Escalas (Sprint 5 / Frente 1).

Concentra as regras que não podem viver só na view/form (P-ARQ-04):

- `create_schedule` valida que a `person` pertence ao `ministry` (M2M
  `Ministry.members`) e **bloqueia conflito** (mesma pessoa em outro encontro na
  mesma data) — salvo `allow_conflict=True`, usado pela aprovação de exceção
  (Frente 2).
- `detect_conflict` devolve as escalas conflitantes (mesma pessoa, mesma data,
  encontro diferente). `Gathering` só tem `date` (sem hora) → o conflito é por
  data.
- `approve_exception` (Frente 2) autoriza um conflito: só **Pastor** ou o
  **Coordenador competente** do ministério; registra `ScheduleConflictApproval`.
  O Secretário, apesar de admin no CRUD, NÃO aprova (decisão Sprint 5).

Auditoria fica fora do service (P-ARQ-06): o AuditLog é automático
(Schedule/ScheduleConflictApproval herdam `AuditLogMixin`, receivers em
`apps/core/signals.py`) e o SecurityLog `schedule_exception_approved` é emitido
pelo signal `post_save` de ScheduleConflictApproval em `apps/schedules/signals.py`.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.schedules.models import Schedule, ScheduleConflictApproval


def detect_conflict(*, person, gathering, exclude_schedule=None):
    """Escalas conflitantes: mesma pessoa, mesma data, em OUTRO encontro.

    Estar escalada duas vezes no MESMO encontro (ministérios distintos) não é
    conflito — a pessoa está no mesmo lugar. Conflito é precisar estar em dois
    encontros diferentes na mesma data. Retorna um queryset (vazio = sem conflito).
    """
    qs = Schedule.objects.filter(person=person, gathering__date=gathering.date).exclude(
        gathering=gathering
    )
    if exclude_schedule is not None:
        qs = qs.exclude(pk=exclude_schedule.pk)
    return qs.select_related('gathering', 'ministry')


def create_schedule(
    *, ministry, person, gathering, role='', notes='', allow_conflict=False
):
    """Cria uma escala validando vínculo ao ministério e bloqueando conflito.

    - `person` precisa pertencer ao `ministry` (M2M `Ministry.members`), senão
      `ValidationError`.
    - Se houver conflito (mesma pessoa/data, outro encontro) e `allow_conflict` for
      `False`, `ValidationError` — o override só vem da aprovação de exceção
      (Frente 2), que chama com `allow_conflict=True`.

    Retorna o `Schedule` criado.
    """
    if not ministry.members.filter(pk=person.pk).exists():
        raise ValidationError(
            'A pessoa precisa pertencer ao ministerio para ser escalada.'
        )

    if (
        not allow_conflict
        and detect_conflict(person=person, gathering=gathering).exists()
    ):
        raise ValidationError(
            'Conflito: a pessoa ja esta escalada em outro encontro nesta data. '
            'Use a aprovacao de excecao para autorizar.'
        )

    return Schedule.objects.create(
        ministry=ministry,
        person=person,
        gathering=gathering,
        role=role or '',
        notes=notes or '',
    )


def is_competent_approver(user, ministry):
    """Quem pode aprovar exceção de conflito no `ministry` (§3.7).

    Pastor (qualquer ministério) ou o Coordenador do ministério (`coordinators`
    → user_id). O Secretário NÃO aprova (decisão Sprint 5), mesmo sendo admin no
    CRUD — por isso a checagem é por `pastor`/coordenação, nunca por `secretary`.
    """
    if user.has_any_role('pastor'):
        return True
    return ministry.coordinators.filter(user_id=user.id).exists()


def approve_exception(
    *, actor, ministry, person, gathering, justification, role='', notes=''
):
    """Cria uma escala em conflito COM aprovação explícita (§3.7).

    Barreiras: `actor` precisa ser aprovador competente (`is_competent_approver`);
    `justification` é obrigatória; tem de HAVER conflito (senão é criação normal).
    Cria o `Schedule` (via `create_schedule(allow_conflict=True)` — revalida vínculo
    ao ministério) + um `ScheduleConflictApproval`, e emite SecurityLog
    `schedule_exception_approved`. Retorna `(schedule, approval)`.
    """
    if not is_competent_approver(actor, ministry):
        raise ValidationError(
            'Apenas o Pastor ou o Coordenador do ministerio aprova excecao.'
        )
    if not (justification or '').strip():
        raise ValidationError('Justificativa e obrigatoria para aprovar excecao.')
    if not detect_conflict(person=person, gathering=gathering).exists():
        raise ValidationError(
            'Nao ha conflito nesta data; use a criacao normal de escala.'
        )

    schedule = create_schedule(
        ministry=ministry,
        person=person,
        gathering=gathering,
        role=role,
        notes=notes,
        allow_conflict=True,
    )
    # O SecurityLog `schedule_exception_approved` é emitido pelo signal
    # `post_save` de ScheduleConflictApproval (apps/schedules/signals.py, P-ARQ-06);
    # o AuditLog vem dos receivers globais de AuditLogMixin (apps/core/signals.py).
    approval = ScheduleConflictApproval.objects.create(
        schedule=schedule,
        approved_by_id=actor.id,
        justification=justification.strip(),
        approved_at=timezone.now(),
    )
    return schedule, approval
