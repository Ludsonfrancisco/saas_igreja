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

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from apps.gatherings.models import Attendance
from apps.people.models import Person

# Janela de presenca "ultimo mes" (~30 dias). RF-071: presenca recente.
ATTENDANCE_WINDOW_DAYS = 30


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
    from apps.ministries.models import Ministry

    qs = Ministry.objects.filter(is_active=True)
    if ministry_ids is not None:
        qs = qs.filter(id__in=ministry_ids)
    return qs.count()
