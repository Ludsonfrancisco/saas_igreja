"""Metricas do dashboard, escopadas por papel (Sprint 6 / Bloco 5).

RF-070..072 (dashboard por papel) / ACCESS_MATRIX §3.9. Toda a logica de metrica
vive aqui (P-ARQ-04: a view so monta contexto). As contas saem 100% de agregacao
no banco (`Count`/`aggregate`/`annotate`) — nunca laco Python sobre queryset
(P-ARQ-09; nplusone levanta em teste).

Multi-tenancy: estas funcoes assumem que o schema do tenant JA esta ativo
(resolvido pelo `TenantMiddleware` na request, ou por `schema_context` no teste).
`Person`/`Community`/`Ministry`/`Gathering`/`Attendance` sao todos TENANT_APPS, logo
as querysets veem APENAS a igreja atual — nao ha vazamento cross-tenant (TENANT-04).

Semantica de recorte (3 niveis de escopo)
------------------------------------------
`church_metrics(*, community_ids=None, ministry_ids=None)`:

- ambos `None` (default) => VISAO COMPLETA da igreja (Pastor, §3.9 "completo").
- `community_ids` (iteravel de ids) => recorta as comunidades que o usuario LIDERA
  (Lider de Comunidade, §3.9 "simplificado da comunidade"):
    * Pessoas: `Person.community__in=community_ids`.
    * Presenca: `Attendance` de `Gathering`s cuja `community` esta no escopo
      (o vinculo Gathering->Community EXISTE no schema — §5.6).
- `ministry_ids` => recorta os ministerios que o usuario COORDENA (Coordenador,
  §3.9 "simplificado do ministerio"):
    * Pessoas: `Person.ministries__in=ministry_ids` (M2M Person<->Ministry).
    * Presenca: NAO existe vinculo Gathering->Ministry no schema. Recortamos a
      presenca pela ASSOCIACAO Person<->Ministry — `Attendance.person.ministries__in`
      (presenca das pessoas DAQUELE ministerio, em qualquer encontro). Decisao
      documentada (a alternativa — encontro por ministerio — nao tem suporte no
      data model atual).

Recorte CONSERVADOR (P-ARQ-08): passar `community_ids`/`ministry_ids` VAZIO (set
vazio) NAO cai para a visao completa — devolve metrica zerada. Quem chama (a view)
passa o conjunto de comunidades/ministerios do usuario; se ele nao lidera nada, o
conjunto e vazio e ele ve zeros, nunca os numeros da igreja inteira.
"""

import calendar as _calendar
from datetime import date, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.gatherings.models import Attendance, Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person

# Janela de presenca "ultimo mes" (~30 dias). RF-071: presenca recente.
ATTENDANCE_WINDOW_DAYS = 30

# Quantos encontros futuros o card "Próximas programações" da home exibe (RF-103).
UPCOMING_GATHERINGS_LIMIT = 5

# Rótulos pt-BR do calendário da home (RF-102). Semana começa no DOMINGO (Brasil).
MONTH_NAMES_PT = (
    '',
    'Janeiro',
    'Fevereiro',
    'Março',
    'Abril',
    'Maio',
    'Junho',
    'Julho',
    'Agosto',
    'Setembro',
    'Outubro',
    'Novembro',
    'Dezembro',
)
WEEKDAY_LABELS_PT = ('Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb')


def church_metrics(*, community_ids=None, ministry_ids=None):
    """Calcula as metricas da igreja no escopo dado (dict serializavel).

    Escopo (ver docstring do modulo): ambos `None` = visao completa; `community_ids`
    recorta as comunidades lideradas; `ministry_ids` recorta os ministerios
    coordenados. Conjunto vazio => metrica zerada (conservador), nunca completa.

    Retorna um dict de numeros (pronto para template e para um futuro Chart.js):

        {
            'people_total': int,
            'people_by_status': {<status>: int, ...},  # todos os status, inclui 0
            'attendance_last_month': int,  # presencas (is_present) na janela
            'active_communities': int,
            'active_ministries': int,
            'scope': 'church' | 'community' | 'ministry',
        }
    """
    scope, person_qs = _scoped_person_queryset(
        community_ids=community_ids, ministry_ids=ministry_ids
    )
    return {
        'people_total': person_qs.count(),
        'people_by_status': _people_by_status(person_qs),
        'attendance_last_month': _attendance_last_month(
            community_ids=community_ids, ministry_ids=ministry_ids
        ),
        'active_communities': _active_communities(community_ids=community_ids),
        'active_ministries': _active_ministries(ministry_ids=ministry_ids),
        'scope': scope,
    }


def _scoped_person_queryset(*, community_ids, ministry_ids):
    """(scope_label, Person queryset) recortado ao escopo pedido.

    `distinct()` no recorte por ministerio: o join no M2M `Person.ministries` pode
    duplicar linhas de Person quando ela esta em >1 ministerio do escopo.
    """
    qs = Person.objects.all()
    if community_ids is not None:
        return 'community', qs.filter(community_id__in=community_ids)
    if ministry_ids is not None:
        return 'ministry', qs.filter(ministries__in=ministry_ids).distinct()
    return 'church', qs


def _people_by_status(person_qs):
    """Contagem por status via UM group-by no banco (P-ARQ-09).

    Inicia o dict com TODOS os `Person.Status` em 0 e sobrescreve com o que o
    group-by retornar — o template recebe todas as chaves, mesmo status sem pessoa.
    """
    counts = {status: 0 for status in Person.Status.values}
    rows = person_qs.values('status').annotate(total=Count('id'))
    for row in rows:
        counts[row['status']] = row['total']
    return counts


def _attendance_last_month(*, community_ids, ministry_ids):
    """Presencas (is_present) nos ultimos ~30 dias, dentro do escopo.

    Filtra pela `Gathering.date` (data do encontro, nao `created_at`). Escopo:
    - comunidade: encontros das comunidades lideradas (`gathering__community__in`);
    - ministerio: presencas das pessoas do(s) ministerio(s) coordenado(s)
      (`person__ministries__in`) — nao ha vinculo Gathering->Ministry (ver modulo).
    """
    since = timezone.now().date() - timedelta(days=ATTENDANCE_WINDOW_DAYS)
    qs = Attendance.objects.filter(is_present=True, gathering__date__gte=since)
    if community_ids is not None:
        qs = qs.filter(gathering__community_id__in=community_ids)
    elif ministry_ids is not None:
        qs = qs.filter(person__ministries__in=ministry_ids)
    # distinct: o join em person__ministries pode duplicar a linha de Attendance.
    return qs.distinct().count()


def _active_communities(*, community_ids):
    """Comunidades ativas. No escopo de comunidade, conta so as do escopo."""
    from apps.communities.models import Community

    qs = Community.objects.filter(is_active=True)
    if community_ids is not None:
        qs = qs.filter(id__in=community_ids)
    return qs.count()


def _active_ministries(*, ministry_ids):
    """Ministerios ativos. No escopo de ministerio, conta so os do escopo."""
    qs = Ministry.objects.filter(is_active=True)
    if ministry_ids is not None:
        qs = qs.filter(id__in=ministry_ids)
    return qs.count()


# --------------------------------------------------------------------------- #
# Home nova (Sprint 6.6 / Bloco 2) — agenda + GAP de voluntários
# --------------------------------------------------------------------------- #
#
# Tres agregados independentes que alimentam a home (RF-102/103/104). Todos saem de
# agregacao no banco do TENANT ATUAL (P-ARQ-09: zero laco/N+1; o isolamento por
# tenant e automatico — `Gathering`/`Ministry`/`Person` sao TENANT_APPS, TENANT-04).


def upcoming_gatherings(*, today=None, limit=UPCOMING_GATHERINGS_LIMIT):
    """Proximos encontros (futuros), ordenados por data ascendente (RF-103).

    Visibilidade: como na lista de Encontros (§3.6), todos os papeis de gestao veem
    TODOS os encontros da igreja — so a EDICAO e escopada. O recorte aqui e apenas
    o tenant (automatico) + o filtro "data >= hoje". `select_related('community')`
    evita N+1 ao exibir a comunidade de cada encontro no card.

    Retorna um queryset (preguicoso) ja fatiado em `limit`.
    """
    today = today or timezone.now().date()
    return (
        Gathering.objects.filter(date__gte=today)
        .select_related('community')
        .order_by('date', 'created_at')[:limit]
    )


def event_days(*, year, month):
    """Dias do mes (`year`/`month`) com >=1 encontro, como `set` de inteiros (RF-102).

    UM group-by no banco (`date__day` + `distinct`): nunca itera `Gathering` em
    Python (P-ARQ-09). Usado pelo calendario da home para marcar os dias com evento.
    """
    rows = (
        Gathering.objects.filter(date__year=year, date__month=month)
        .values_list('date__day', flat=True)
        .distinct()
    )
    return set(rows)


def build_calendar_weeks(*, year, month, event_days, today):
    """Matriz do calendario do mes (RF-102) — lista de semanas, cada uma com 7 dias.

    Funcao PURA (sem banco): recebe `event_days` (set de dias do mes com encontro,
    de `event_days()`) e `today` ja resolvidos. Semana inicia no DOMINGO. As celulas
    de transbordo (mes anterior/seguinte) vem com `in_month=False` para a UI esmaecer.

    Cada celula: `{'day', 'date' (ISO), 'in_month', 'is_today', 'has_event'}`.
    `has_event` so e True para dias DO mes (o marcador segue o `event_days` do mes
    exibido). `date` ISO habilita o `hx-get` "encontros do dia".
    """
    cal = _calendar.Calendar(firstweekday=6)  # 6 = domingo
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        row = []
        for d in week:
            in_month = d.month == month and d.year == year
            row.append(
                {
                    'day': d.day,
                    'date': d.isoformat(),
                    'in_month': in_month,
                    'is_today': d == today,
                    'has_event': in_month and d.day in event_days,
                }
            )
        weeks.append(row)
    return weeks


def gatherings_on_day(day):
    """Encontros de um dia (`day` = date), ordenados — clique no calendário (RF-102).

    Visibilidade do tenant inteiro (como a lista de Encontros, §3.6).
    `select_related('community')` evita N+1 ao exibir a comunidade de cada encontro.
    """
    return (
        Gathering.objects.filter(date=day)
        .select_related('community')
        .order_by('created_at')
    )


def ministry_health(*, ministry_ids=None):
    """Saúde do Ministério (RF-104 / OD-029) — GAP agregado em % + por ministério.

    `pct` = taxa de preenchimento de voluntários = Σmin(atuais, meta) / Σmeta × 100
    (cap em 100% por ministério; ministérios com meta 0 não entram no denominador).
    É o GAP expresso como saúde — dado REAL, não score inventado. Reusa
    `ministry_volunteer_gaps` (uma query agregada, P-ARQ-09).

    Retorna `{'pct', 'items', 'total', 'met'}` (items = lista dos gaps por ministério).
    """
    items = ministry_volunteer_gaps(ministry_ids=ministry_ids)
    total_needed = sum(m['needed'] for m in items)
    filled = sum(min(m['current'], m['needed']) for m in items if m['needed'])
    pct = round(filled / total_needed * 100) if total_needed else 100
    return {
        'pct': pct,
        'items': items,
        'total': len(items),
        'met': sum(1 for m in items if m['is_met']),
    }


def _month_starts(months, today):
    """Lista dos primeiros-dias dos últimos `months` meses (mais antigo → atual)."""
    starts = []
    y, m = today.year, today.month
    for _ in range(months):
        starts.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(starts))


def _cumulative_by_month(qs, *, field, month_starts):
    """Contagem CUMULATIVA por mês de `qs` pelo `field` (datetime), zero N+1.

    UM group-by (`TruncMonth` + `Count`) no banco; o acumulado é montado em Python
    sobre o resultado (poucas linhas, sem query por mês — P-ARQ-09).
    """
    rows = qs.annotate(_m=TruncMonth(field)).values('_m').annotate(_n=Count('id'))
    per_month = {}
    for row in rows:
        key = row['_m']
        if key is not None:
            per_month[(key.year, key.month)] = row['_n']
    # Acumulado até o fim de cada mês exibido (inclui tudo anterior à janela).
    before = sum(
        n
        for (yy, mm), n in per_month.items()
        if (yy, mm) < (month_starts[0].year, month_starts[0].month)
    )
    series = []
    running = before
    for start in month_starts:
        running += per_month.get((start.year, start.month), 0)
        series.append(running)
    return series


def home_growth_series(*, months=6, today=None):
    """Séries REAIS de crescimento p/ os sparklines dos KPIs da home.

    Cumulativo por mês (últimos `months`) de Pessoas (não-anonimizadas) e Comunidades
    ativas, e contagem de Escalas criadas por mês. Tudo agregado no banco do tenant
    (P-ARQ-09). Retorna `{'labels', 'people', 'communities', 'schedules'}`.
    """
    from apps.communities.models import Community
    from apps.schedules.models import Schedule

    today = today or timezone.localdate()
    starts = _month_starts(months, today)
    labels = [_calendar.month_abbr[s.month] for s in starts]
    people = _cumulative_by_month(
        Person.objects.filter(anonymized_at__isnull=True),
        field='created_at',
        month_starts=starts,
    )
    communities = _cumulative_by_month(
        Community.objects.filter(is_active=True),
        field='created_at',
        month_starts=starts,
    )
    schedules = _cumulative_by_month(
        Schedule.objects.all(), field='created_at', month_starts=starts
    )
    return {
        'labels': labels,
        'people': people,
        'communities': communities,
        'schedules': schedules,
    }


def ministry_volunteer_gaps(*, ministry_ids=None):
    """GAP de voluntarios por ministerio ativo — card "Saude do Ministerio" (RF-104).

    OD-029: "voluntarios atuais" = numero de `Person` em `ministry.members`
    (M2M `Person.ministries`), excluindo anonimizadas. Meta = `volunteers_needed`.
    GAP = `max(meta - atuais, 0)` (quantos faltam). A contagem sai de UM `annotate`
    no banco (P-ARQ-09) — nao ha `Count` por linha nem laco com query.

    Escopo (3 niveis, igual ao resto do dashboard, P-ARQ-08):
    - `ministry_ids=None` (default) => todos os ministerios ativos (Pastor, §3.9);
    - `ministry_ids` (iteravel) => recorta aos ministerios coordenados (Coordenador);
      conjunto VAZIO => lista vazia (conservador, nunca a visao completa).

    Retorna uma lista de dicts ordenada por nome (serializavel p/ o template):

        [{'id', 'name', 'current', 'needed', 'gap', 'is_met'}, ...]
    """
    qs = Ministry.objects.filter(is_active=True)
    if ministry_ids is not None:
        qs = qs.filter(id__in=ministry_ids)
    qs = qs.annotate(
        current=Count(
            'members',
            filter=Q(members__anonymized_at__isnull=True),
            distinct=True,
        )
    ).order_by('name')
    # Iterar o queryset materializa as linhas ja com `current` (annotate) e
    # `volunteers_needed`/`name` (colunas) — sem query adicional por ministerio.
    return [
        {
            'id': ministry.id,
            'name': ministry.name,
            'current': ministry.current,
            'needed': ministry.volunteers_needed,
            'gap': max(ministry.volunteers_needed - ministry.current, 0),
            'is_met': ministry.current >= ministry.volunteers_needed,
        }
        for ministry in qs
    ]
