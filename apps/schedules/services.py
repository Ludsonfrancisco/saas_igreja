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
from django.db.models import Q
from django.utils import timezone

from apps.gatherings.models import Gathering
from apps.ministries.models import Ministry
from apps.schedules.models import (
    MinistryEventOptOut,
    Schedule,
    ScheduleConflictApproval,
)


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


# === Escalas v2 (coordenador-cêntrica) =======================================
# RF-111..116 / RN-020..023. Reusa Schedule/ScheduleConflictApproval; adiciona
# escopo do coordenador, janela de pendência configurável e opt-out por evento.


def coordinated_ministries(user, *, qs=None):
    """Ministérios no escopo do `user` (RN-020).

    Pastor/Secretário enxergam **todos** (visão consolidada); o coordenador, só os
    que coordena (`coordinators__user_id`, M2M OD-019). Reflete `ScopedToMinistryMixin`
    na camada de service (P-ARQ-08).
    """
    qs = qs if qs is not None else Ministry.objects.all()
    if user.has_any_role('pastor', 'secretary'):
        return qs
    return qs.filter(coordinators__user_id=user.id).distinct()


def _next_month(year, month):
    """(ano, mês) do mês seguinte a (year, month)."""
    return (year + 1, 1) if month == 12 else (year, month + 1)


def is_pending_window(event_date, *, today, open_day):
    """Um evento entra na janela de pendência? (RF-116 / RN-023).

    - Mês corrente: **sempre** na janela.
    - Mês seguinte: só quando `today.day >= open_day` (default 25, configurável por
      igreja em `Church.schedule_pending_open_day`).
    - Demais meses (passados ou m+2 em diante): fora.
    """
    if (event_date.year, event_date.month) == (today.year, today.month):
        return True
    nm = _next_month(today.year, today.month)
    if (event_date.year, event_date.month) == nm and today.day >= open_day:
        return True
    return False


def active_window_gatherings(*, today, open_day, qs=None):
    """Queryset de `Gathering` dentro da janela ativa de pendência (RF-116)."""
    qs = qs if qs is not None else Gathering.objects.all()
    cond = Q(date__year=today.year, date__month=today.month)
    if today.day >= open_day:
        nm_year, nm_month = _next_month(today.year, today.month)
        cond |= Q(date__year=nm_year, date__month=nm_month)
    return qs.filter(cond)


def set_optout(*, ministry, gathering, actor, reason=''):
    """Marca opt-out de um ministério num evento (RF-114 / RN-022).

    Só o **coordenador daquele ministério** marca (decisão OD-031.b, coordenador-
    cêntrica). Idempotente: `update_or_create` por `(ministry, gathering)`.
    """
    if not ministry.coordinators.filter(user_id=actor.id).exists():
        raise ValidationError(
            'Apenas o coordenador do ministerio marca "nao atuaremos nesse evento".'
        )
    optout, _ = MinistryEventOptOut.objects.update_or_create(
        ministry=ministry,
        gathering=gathering,
        defaults={'marked_by_id': actor.id, 'reason': (reason or '').strip()},
    )
    return optout


def remove_optout(*, ministry, gathering, actor):
    """Remove o opt-out (RN-022): coordenador do ministério OU Pastor/Secretário."""
    is_coordinator = ministry.coordinators.filter(user_id=actor.id).exists()
    if not (actor.has_any_role('pastor', 'secretary') or is_coordinator):
        raise ValidationError('Sem permissao para remover o opt-out deste ministerio.')
    MinistryEventOptOut.objects.filter(ministry=ministry, gathering=gathering).delete()


def ministry_roster(*, ministry, gathering):
    """Roster de escalação de um ministério para um evento (RF-112/113).

    Devolve a lista de membros (`ministry.members`) com dois sinalizadores, calculados
    em 2 queries (sem N+1, P-ARQ-09):

    - `scheduled_here`: já escalado NESTE evento por ESTE ministério.
    - `conflict_elsewhere`: já escalado em OUTRO encontro na MESMA data (→ cinza,
      RF-113; escalável só via `approve_exception`).

    Cada item: `{'person', 'scheduled_here', 'conflict_elsewhere'}`.
    """
    members = list(ministry.members.all())
    member_ids = [p.pk for p in members]
    here_ids = set(
        Schedule.objects.filter(
            gathering=gathering, ministry=ministry, person_id__in=member_ids
        ).values_list('person_id', flat=True)
    )
    conflict_ids = set(
        Schedule.objects.filter(
            person_id__in=member_ids, gathering__date=gathering.date
        )
        .exclude(gathering=gathering)
        .values_list('person_id', flat=True)
    )
    return [
        {
            'person': p,
            'scheduled_here': p.pk in here_ids,
            'conflict_elsewhere': p.pk in conflict_ids,
        }
        for p in members
    ]


def can_manage_ministry(user, ministry):
    """O `user` pode escalar/opt-out neste `ministry`? (RN-020, escopo do modal).

    Pastor/Secretário (admin) ou o coordenador do ministério. Espelha a barreira
    de escopo da view (defesa em profundidade, P-ARQ-08).
    """
    if user.has_any_role('pastor', 'secretary'):
        return True
    return ministry.coordinators.filter(user_id=user.id).exists()


def schedule_members_bulk(*, ministry, gathering, person_ids, actor):
    """Escala vários voluntários de um ministério num evento (RF-112).

    Aditivo: cria `Schedule` para cada `person_id` ainda não escalado neste evento.
    Ignora quem não é membro/escopo e quem está em **conflito de data** (esses só
    entram via `approve_exception`, RF-113). Retorna `(criados, em_conflito)`.

    Barreira de escopo: só Pastor/Secretário ou o coordenador do ministério (RN-020).
    """
    if not can_manage_ministry(actor, ministry):
        raise ValidationError('Sem permissao para escalar neste ministerio.')

    valid_ids = set(
        ministry.members.filter(pk__in=person_ids).values_list('pk', flat=True)
    )
    already = set(
        Schedule.objects.filter(
            gathering=gathering, ministry=ministry, person_id__in=valid_ids
        ).values_list('person_id', flat=True)
    )
    created, conflicted = 0, []
    for person in ministry.members.filter(pk__in=valid_ids - already):
        try:
            create_schedule(ministry=ministry, person=person, gathering=gathering)
            created += 1
        except ValidationError:
            conflicted.append(person)  # conflito de data → via exceção (RF-113)
    return created, conflicted


def pending_ministries_for_gathering(*, gathering, ministries):
    """Dos `ministries` dados, quais estão PENDENTES no `gathering` (sem escala nem
    opt-out). Usado pelo painel e pelo badge de pendência (RF-111/115)."""
    ministry_ids = [m.pk for m in ministries]
    resolved = set(
        Schedule.objects.filter(
            gathering=gathering, ministry_id__in=ministry_ids
        ).values_list('ministry_id', flat=True)
    )
    resolved |= set(
        MinistryEventOptOut.objects.filter(
            gathering=gathering, ministry_id__in=ministry_ids
        ).values_list('ministry_id', flat=True)
    )
    return [m for m in ministries if m.pk not in resolved]


def pending_events_for_user(*, user, open_day, today=None):
    """Eventos da janela ativa com ≥1 ministério pendente para o `user` (RF-115).

    Pendente = ministério do escopo do usuário sem `Schedule` nem `MinistryEventOptOut`
    naquele evento. 3 queries no total (eventos + escalas + opt-outs), sem N+1.
    Devolve um queryset de `Gathering` (ordenado por data).
    """
    today = today or timezone.localdate()
    ministry_ids = list(coordinated_ministries(user).values_list('id', flat=True))
    if not ministry_ids:
        return Gathering.objects.none()

    events = list(
        active_window_gatherings(today=today, open_day=open_day).order_by('date')
    )
    event_ids = [e.pk for e in events]
    resolved = {}  # gathering_id -> set(ministry_id) já escalado OU opt-out
    pairs = list(
        Schedule.objects.filter(
            gathering_id__in=event_ids, ministry_id__in=ministry_ids
        ).values_list('gathering_id', 'ministry_id')
    ) + list(
        MinistryEventOptOut.objects.filter(
            gathering_id__in=event_ids, ministry_id__in=ministry_ids
        ).values_list('gathering_id', 'ministry_id')
    )
    for g_id, m_id in pairs:
        resolved.setdefault(g_id, set()).add(m_id)

    total = len(ministry_ids)
    pending_ids = [e.pk for e in events if len(resolved.get(e.pk, set())) < total]
    return Gathering.objects.filter(pk__in=pending_ids).order_by('date')


def events_with_pending(*, user, open_day, today=None):
    """Eventos da janela ativa com a contagem de ministérios pendentes (RF-111).

    Para a TELA de Escalas por evento: lista TODOS os eventos da janela e, para cada,
    quantos ministérios do escopo do usuário ainda faltam escalar (badge). 3 queries
    no total (sem N+1). Item: `{'gathering', 'pending', 'total'}`.
    """
    today = today or timezone.localdate()
    ministry_ids = list(coordinated_ministries(user).values_list('id', flat=True))
    events = list(
        active_window_gatherings(today=today, open_day=open_day)
        .select_related('community')
        .order_by('date')
    )
    if not ministry_ids:
        return [{'gathering': e, 'pending': 0, 'total': 0} for e in events]

    event_ids = [e.pk for e in events]
    resolved = {}
    pairs = list(
        Schedule.objects.filter(
            gathering_id__in=event_ids, ministry_id__in=ministry_ids
        ).values_list('gathering_id', 'ministry_id')
    ) + list(
        MinistryEventOptOut.objects.filter(
            gathering_id__in=event_ids, ministry_id__in=ministry_ids
        ).values_list('gathering_id', 'ministry_id')
    )
    for g_id, m_id in pairs:
        resolved.setdefault(g_id, set()).add(m_id)

    total = len(ministry_ids)
    return [
        {
            'gathering': e,
            'pending': total - len(resolved.get(e.pk, set())),
            'total': total,
        }
        for e in events
    ]
