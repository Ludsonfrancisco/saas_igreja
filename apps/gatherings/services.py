"""Service layer de Encontros (Sprint 4 / Frente 1).

Camada fina (P-ARQ-04), mas concentra a regra que NÃO pode viver só na view/form:
a **permissão de criar por tipo × papel × escopo** (ACCESS_MATRIX §3.6):

- WORSHIP        → só Pastor/Secretário (admin).
- COMMUNITY      → admin OU Líder de uma comunidade (a comunidade escolhida tem de
                   ser uma que ele lidera); exige `Church.has_communities` (RN-010).
- EVENT/MEETING  → admin OU qualquer Líder/Coordenador (papel `leader`).

`created_by` recebe o `user_id` do ator (TENANT-04) — habilita a trava "editar
pelo criador" da §3.6. AuditLog é automático (AuditLogMixin); o service não chama
`record_audit`.
"""

import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.communities.models import Community
from apps.gatherings.models import Attendance, AttendanceSession, Gathering
from apps.people.models import Person

ADMIN_ROLES = ('pastor', 'secretary')


def _leads_any_community(user):
    """True se `user` lidera ≥1 comunidade (M2M `Community.leaders` → user_id)."""
    return Community.objects.filter(leaders__user_id=user.id).exists()


def _leads_community(user, community):
    """True se `user` lidera a `community` específica (escopo COMMUNITY)."""
    return community.leaders.filter(user_id=user.id).exists()


def allowed_types(user, church):
    """Tipos de encontro que `user` pode criar nesta igreja (§3.6).

    Usado pelo form (limitar o dropdown) e pelo service (validar). Pastor e
    Secretário são admin (todos os tipos). COMMUNITY depende de `has_communities`.
    """
    is_admin = user.has_any_role(*ADMIN_ROLES)
    types = []
    if is_admin:
        types.append(Gathering.Type.WORSHIP)
    if church.has_communities and (is_admin or _leads_any_community(user)):
        types.append(Gathering.Type.COMMUNITY)
    if is_admin or user.has_any_role('leader'):
        types += [Gathering.Type.EVENT, Gathering.Type.MEETING]
    return types


def create_gathering(
    *, church, user, gathering_type, date, title=None, community=None, description=''
):
    """Cria um encontro aplicando a barreira de tipo×papel×escopo (§3.6).

    `user` é o ator (request.user). Levanta `ValidationError` quando o ator não
    pode criar o tipo pedido, ou quando um tipo COMMUNITY vem sem comunidade
    válida/escopada. Retorna o `Gathering` criado.
    """
    # RN-018 (Comunidades v2): criar encontro é administrativo — só Pastor/Secretário.
    # Reforça a barreira da view (defesa em profundidade, P-ARQ-08).
    if not user.has_any_role(*ADMIN_ROLES):
        raise ValidationError('Apenas Pastor ou Secretario podem criar encontros.')
    if gathering_type not in allowed_types(user, church):
        raise ValidationError(
            'Voce nao tem permissao para criar este tipo de encontro.'
        )

    if gathering_type == Gathering.Type.COMMUNITY:
        if community is None:
            raise ValidationError('Selecione a comunidade do encontro.')
        if not user.has_any_role(*ADMIN_ROLES) and not _leads_community(
            user, community
        ):
            raise ValidationError(
                'Voce so pode criar encontros de uma comunidade que lidera.'
            )
    else:
        # Só encontros COMMUNITY têm comunidade — os demais ignoram o campo.
        community = None

    return Gathering.objects.create(
        gathering_type=gathering_type,
        title=title or None,
        date=date,
        community=community,
        description=description or '',
        created_by=user.id,
    )


# --- Presença (Frente 2) -----------------------------------------------------


def attendance_roster(gathering):
    """Pessoas candidatas à lista de presença de um encontro (RF-040).

    - Encontro COMMUNITY com comunidade → membros daquela comunidade.
    - Demais tipos → todas as pessoas ATIVAS da igreja.

    Exclui sempre as anonimizadas (`anonymized_at`). Ordenado por nome.
    """
    qs = Person.objects.filter(anonymized_at__isnull=True)
    if gathering.gathering_type == Gathering.Type.COMMUNITY and gathering.community_id:
        qs = qs.filter(community_id=gathering.community_id)
    else:
        qs = qs.exclude(status=Person.Status.INACTIVE)
    return qs.order_by('name')


def mark_attendance_bulk(*, gathering, present_person_ids):
    """Marca presença em lote (RN-009, idempotente via `update_or_create`).

    `present_person_ids` é o conjunto de Pessoas PRESENTES (vindo dos checkboxes).
    Para cada uma, faz `update_or_create` com `is_present=True` (nunca duplica).
    Pessoas que JÁ tinham presença neste encontro e agora não vieram passam a
    `is_present=False` (mantém o registro histórico do encontro, não cria linha
    para quem nunca foi marcado). Retorna a quantidade de presentes.

    Só aceita ids de Pessoas reais (filtra contra a base) — o schema-per-tenant já
    isola a igreja; isto barra ids forjados/inexistentes (evita IntegrityError).
    """
    valid_ids = set(
        Person.objects.filter(
            id__in=present_person_ids, anonymized_at__isnull=True
        ).values_list('id', flat=True)
    )
    for person_id in valid_ids:
        Attendance.objects.update_or_create(
            person_id=person_id,
            gathering=gathering,
            defaults={'is_present': True},
        )
    # Quem estava marcado presente e não veio agora: vira ausente (não apaga).
    Attendance.objects.filter(gathering=gathering, is_present=True).exclude(
        person_id__in=valid_ids
    ).update(is_present=False)
    return len(valid_ids)


def can_mark_attendance(user, gathering):
    """True se `user` pode marcar presença neste encontro (§3.6).

    Espelha o escopo de EDIÇÃO: Pastor/Secretário (qualquer); Líder/Coordenador só
    o que criou OU encontros de uma comunidade que lidera.
    """
    if user.has_any_role(*ADMIN_ROLES):
        return True
    if gathering.created_by == user.id:
        return True
    if (
        gathering.community_id
        and gathering.community.leaders.filter(user_id=user.id).exists()
    ):
        return True
    return False


def gatherings_in_month(*, year, month):
    """Encontros do mês/ano no tenant atual, ordenados por data (RF-102 / item 4).

    Alimenta a "Agenda do mês" da tela de Encontros — a lista lateral que mostra os
    nomes dos encontros sem precisar clicar dia a dia. `select_related('community')`
    evita N+1 ao exibir o nome da comunidade (P-ARQ-09)."""
    return (
        Gathering.objects.filter(date__year=year, date__month=month)
        .select_related('community')
        .order_by('date', 'gathering_type')
    )


# --- Comunidades v2 — presença da célula (RF-107/108 · RN-016/017) ------------- #


@transaction.atomic
def launch_attendance_session(
    *,
    gathering,
    present_person_ids,
    visitor_names=None,
    note='',
    confirmed_by_id=None,
):
    """Lança a sessão de presença de uma reunião de célula (RF-108 · DM-1/DM-2).

    Faz, numa transação:
    1. cria os VISITANTES informados (só o nome) como `Person` status VISITOR na
       comunidade do encontro (RN-017 · DM-1) e os marca presentes;
    2. marca a presença em lote (reusa `mark_attendance_bulk`, RN-009 idempotente);
    3. faz upsert da `AttendanceSession` com a anotação do dia + confirmação
       (`confirmed_by`/`confirmed_at`, RN-016 · DM-2).

    Retorna `(session, present_count)`.
    """
    visitor_ids = []
    for raw in visitor_names or []:
        name = (raw or '').strip()
        if not name:
            continue
        visitor = Person.objects.create(
            name=name,
            status=Person.Status.VISITOR,
            community=gathering.community,
        )
        visitor_ids.append(visitor.id)

    present_ids = set(present_person_ids or []) | set(visitor_ids)
    present_count = mark_attendance_bulk(
        gathering=gathering, present_person_ids=present_ids
    )

    session, _ = AttendanceSession.objects.update_or_create(
        gathering=gathering,
        defaults={
            'note': note or '',
            'confirmed_at': timezone.now(),
            'confirmed_by': confirmed_by_id,
        },
    )
    return session, present_count


def cell_pending_days(community):
    """Encontros de Comunidade da célula, com status lançado/pendente (RF-107).

    "Lançado" = existe `AttendanceSession` confirmada para o encontro. Anota
    `is_launched` no banco (Exists, sem N+1) para a tela "dias a lançar" da célula.
    Mais recentes primeiro."""
    from django.db.models import Exists, OuterRef

    launched = AttendanceSession.objects.filter(
        gathering=OuterRef('pk'), confirmed_at__isnull=False
    )
    return (
        Gathering.objects.filter(
            gathering_type=Gathering.Type.COMMUNITY, community=community
        )
        .annotate(is_launched=Exists(launched))
        .order_by('-date')
    )


def _last_month_starts(months, today):
    """Primeiros-dias dos últimos `months` meses (mais antigo → atual)."""
    starts, y, m = [], today.year, today.month
    for _ in range(months):
        starts.append(datetime.date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(starts))


def monthly_attendance_series(*, months=6, today=None):
    """Total de PRESENÇAS por mês nos últimos `months` (RF-120, gráfico de linha).

    Conta `Attendance(is_present=True)` agrupado pelo mês do encontro
    (`gathering__date`), em 1 query (sem N+1). Retorna `{labels, values}`.
    """
    import calendar as _calendar

    from django.db.models import Count
    from django.db.models.functions import TruncMonth

    today = today or timezone.localdate()
    starts = _last_month_starts(months, today)
    rows = (
        Attendance.objects.filter(is_present=True, gathering__date__gte=starts[0])
        .annotate(month=TruncMonth('gathering__date'))
        .values('month')
        .annotate(n=Count('id'))
    )
    by_month = {(r['month'].year, r['month'].month): r['n'] for r in rows}
    return {
        'labels': [_calendar.month_abbr[s.month] for s in starts],
        'values': [by_month.get((s.year, s.month), 0) for s in starts],
    }


def gatherings_page_stats(*, today=None):
    """KPIs da tela de Encontros (RF-120). Church-wide (§3.6: todos veem todos os
    encontros). Cards: encontros no mês, presenças no mês, média por encontro,
    próximo encontro. Poucas queries agregadas (sem N+1)."""
    today = today or timezone.localdate()
    n_events = Gathering.objects.filter(
        date__year=today.year, date__month=today.month
    ).count()
    present_month = Attendance.objects.filter(
        is_present=True,
        gathering__date__year=today.year,
        gathering__date__month=today.month,
    ).count()
    avg_per_event = round(present_month / n_events, 1) if n_events else 0
    next_event = (
        Gathering.objects.filter(date__gte=today).order_by('date').only('date').first()
    )

    cards = [
        {'label': 'Encontros no mês', 'value': n_events, 'icon': 'calendar'},
        {'label': 'Presenças no mês', 'value': present_month, 'icon': 'calendar-check'},
        {'label': 'Média por encontro', 'value': avg_per_event, 'icon': 'trending-up'},
        {
            'label': 'Próximo encontro',
            'value': next_event.date.strftime('%d/%m') if next_event else '—',
            'icon': 'calendar-clock',
        },
    ]
    return {'cards': cards, 'chart': monthly_attendance_series(today=today)}


def cells_with_pending(communities):
    """Conjunto de `community_id` com ≥1 encontro de Comunidade **não lançado**
    (RF-119, card "células com lançamento pendente"). 1 query, sem N+1."""
    from django.db.models import Exists, OuterRef

    launched = AttendanceSession.objects.filter(
        gathering=OuterRef('pk'), confirmed_at__isnull=False
    )
    rows = (
        Gathering.objects.filter(
            gathering_type=Gathering.Type.COMMUNITY, community__in=communities
        )
        .annotate(is_launched=Exists(launched))
        .filter(is_launched=False)
        .values_list('community', flat=True)
        .distinct()
    )
    return set(rows)


def cell_attendance_summary(community, *, limit=4):
    """Resumo de frequência de UMA célula (RF-109) — para o card no detalhe.

    Olha as últimas `limit` sessões CONFIRMADAS da célula e devolve quantidade de
    sessões, presentes da última e média de presentes. Sem sessões → tudo None."""
    from django.db.models import Count, Q

    rows = list(
        Gathering.objects.filter(
            gathering_type=Gathering.Type.COMMUNITY,
            community=community,
            session__confirmed_at__isnull=False,
        )
        .annotate(present=Count('attendances', filter=Q(attendances__is_present=True)))
        .order_by('-date')[:limit]
    )
    if not rows:
        return {'sessions': 0, 'last_present': None, 'avg_present': None}
    presents = [g.present for g in rows]
    return {
        'sessions': len(presents),
        'last_present': presents[0],
        'avg_present': round(sum(presents) / len(presents), 1),
    }


def cell_frequencies(communities):
    """`{community_id: {'sessions': n, 'avg_present': x}}` para a LISTA de Comunidades
    (RF-109) numa ÚNICA query (sem N+1). Conta só sessões confirmadas."""
    from django.db.models import Count, Q

    rows = (
        Gathering.objects.filter(
            gathering_type=Gathering.Type.COMMUNITY,
            community__in=communities,
            session__confirmed_at__isnull=False,
        )
        .values('community')
        .annotate(
            sessions=Count('id', distinct=True),
            present=Count('attendances', filter=Q(attendances__is_present=True)),
        )
    )
    summary = {}
    for row in rows:
        sessions = row['sessions'] or 0
        summary[row['community']] = {
            'sessions': sessions,
            'avg_present': round(row['present'] / sessions, 1) if sessions else 0,
        }
    return summary
