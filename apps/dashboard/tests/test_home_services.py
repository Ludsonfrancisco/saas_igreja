"""Sprint 6.6 / Bloco 2 — services da home: agenda + GAP de voluntários.

Cobertura (RF-102/103/104 + OD-029):
- `ministry_volunteer_gaps`: atuais = membros não-anonimizados; GAP = max(meta-X,0);
  `is_met`; ordena por nome; ignora ministério inativo; escopo por `ministry_ids`
  (vazio => lista vazia, conservador);
- `event_days`: dias DISTINTOS do mês/tenant com encontro; outro mês não conta;
- `upcoming_gatherings`: só futuros, ordem ascendente por data, respeita `limit`.

Models de TENANT_APPS -> `schema_context` para ORM puro. DDL de criar Church exige
`@pytest.mark.django_db(transaction=True)`.
"""

from datetime import date, timedelta

import pytest
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.dashboard.services import (
    build_calendar_weeks,
    event_days,
    gatherings_on_day,
    home_growth_series,
    ministry_health,
    ministry_volunteer_gaps,
    upcoming_gatherings,
)
from apps.gatherings.models import Gathering
from apps.ministries.models import Ministry
from apps.people.models import Person


@pytest.fixture(autouse=True)
def _reset_schema():
    yield
    connection.set_schema_to_public()


def _gathering(d, title=None):
    return Gathering.objects.create(
        gathering_type=Gathering.Type.WORSHIP, title=title, date=d
    )


# --------------------------------------------------------------------------- #
# GAP de voluntários (RF-104 / OD-029)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_ministry_volunteer_gap(church_a):
    """Atuais = membros não-anonimizados; GAP = max(meta - atuais, 0); is_met."""
    with schema_context(church_a.schema_name):
        louvor = Ministry.objects.create(name='Louvor', volunteers_needed=4)
        diaconia = Ministry.objects.create(name='Diaconia', volunteers_needed=2)
        Ministry.objects.create(name='Acolhimento', volunteers_needed=0)

        # Louvor: 2 membros ativos + 1 anonimizado (não conta) => atuais=2, gap=2.
        for i in range(2):
            Person.objects.create(name=f'L{i}').ministries.add(louvor)
        Person.objects.create(name='Anon', anonymized_at=timezone.now()).ministries.add(
            louvor
        )

        # Diaconia: 3 membros, meta 2 => atuais=3, gap=0, is_met=True.
        for i in range(3):
            Person.objects.create(name=f'D{i}').ministries.add(diaconia)

        gaps = ministry_volunteer_gaps()

    # Ordenado por nome: Acolhimento, Diaconia, Louvor.
    assert [g['name'] for g in gaps] == ['Acolhimento', 'Diaconia', 'Louvor']
    by_name = {g['name']: g for g in gaps}
    assert by_name['Louvor'] == {
        'id': louvor.id,
        'name': 'Louvor',
        'current': 2,  # anonimizado não conta
        'needed': 4,
        'gap': 2,
        'is_met': False,
    }
    assert by_name['Diaconia']['gap'] == 0
    assert by_name['Diaconia']['is_met'] is True
    # Sem meta (needed=0): atuais 0 >= 0 => is_met True, gap 0.
    assert by_name['Acolhimento']['gap'] == 0
    assert by_name['Acolhimento']['is_met'] is True


@pytest.mark.django_db(transaction=True)
def test_ministry_health_pct(church_a):
    """`pct` = Σmin(atuais, meta) / Σmeta × 100 (cap 100% por ministério)."""
    with schema_context(church_a.schema_name):
        louvor = Ministry.objects.create(name='Louvor', volunteers_needed=4)
        acolhida = Ministry.objects.create(name='Acolhida', volunteers_needed=2)
        for i in range(2):  # Louvor 2/4 => preenchido 2
            Person.objects.create(name=f'L{i}').ministries.add(louvor)
        for i in range(3):  # Acolhida 3/2 => preenchido cap 2, is_met True
            Person.objects.create(name=f'A{i}').ministries.add(acolhida)
        health = ministry_health()
    assert health['total'] == 2
    assert health['met'] == 1  # só Acolhida bateu a meta
    assert health['pct'] == round((2 + 2) / (4 + 2) * 100)  # 67


@pytest.mark.django_db(transaction=True)
def test_ministry_health_pct_without_meta_is_100(church_a):
    """Sem nenhuma meta (volunteers_needed=0) => 100% (nada a preencher)."""
    with schema_context(church_a.schema_name):
        Ministry.objects.create(name='Sem meta', volunteers_needed=0)
        assert ministry_health()['pct'] == 100


@pytest.mark.django_db(transaction=True)
def test_home_growth_series_real(church_a):
    """Série de crescimento: `months` pontos, cumulativa, conta o que existe."""
    with schema_context(church_a.schema_name):
        Person.objects.create(name='P1')
        Person.objects.create(name='P2')
        series = home_growth_series(months=6)
    assert len(series['labels']) == 6
    assert len(series['people']) == 6
    # Criadas agora => entram no último mês (cumulativo termina em 2).
    assert series['people'][-1] == 2


@pytest.mark.django_db(transaction=True)
def test_ministry_gap_ignores_inactive(church_a):
    """Ministério inativo não aparece no GAP."""
    with schema_context(church_a.schema_name):
        Ministry.objects.create(name='Ativo', volunteers_needed=1)
        Ministry.objects.create(name='Inativo', is_active=False, volunteers_needed=1)
        gaps = ministry_volunteer_gaps()
    assert [g['name'] for g in gaps] == ['Ativo']


@pytest.mark.django_db(transaction=True)
def test_ministry_gap_scoped_by_ids(church_a):
    """`ministry_ids` recorta; conjunto vazio => lista vazia (conservador)."""
    with schema_context(church_a.schema_name):
        mine = Ministry.objects.create(name='Meu', volunteers_needed=1)
        Ministry.objects.create(name='Alheio', volunteers_needed=1)

        scoped = ministry_volunteer_gaps(ministry_ids=[mine.id])
        empty = ministry_volunteer_gaps(ministry_ids=[])

    assert [g['name'] for g in scoped] == ['Meu']
    assert empty == []


# --------------------------------------------------------------------------- #
# Calendário — dias com evento (RF-102)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_calendar_event_days(church_a):
    """Dias DISTINTOS do mês com encontro; dois encontros no mesmo dia => 1 dia."""
    with schema_context(church_a.schema_name):
        _gathering(date(2026, 6, 5))
        _gathering(date(2026, 6, 5))  # mesmo dia => não duplica
        _gathering(date(2026, 6, 20))
        _gathering(date(2026, 7, 1))  # outro mês => fora

        days = event_days(year=2026, month=6)

    assert days == {5, 20}


# --------------------------------------------------------------------------- #
# Próximas programações (RF-103)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_upcoming_gatherings_future_ordered_limited(church_a):
    """Só futuros (>= hoje), ordem ascendente por data, respeita `limit`."""
    today = timezone.localdate()
    with schema_context(church_a.schema_name):
        _gathering(today - timedelta(days=1), title='Passado')  # não entra
        _gathering(today, title='Hoje')  # entra (>= hoje)
        for i in range(1, 7):
            _gathering(today + timedelta(days=i), title=f'F{i}')

        result = list(upcoming_gatherings(today=today, limit=3))

    titles = [g.title for g in result]
    assert titles == ['Hoje', 'F1', 'F2']  # ascendente, sem o passado, cortado em 3


@pytest.mark.django_db(transaction=True)
def test_gatherings_on_day(church_a):
    """`gatherings_on_day` traz só os encontros daquela data exata."""
    with schema_context(church_a.schema_name):
        _gathering(date(2026, 6, 5), title='No dia')
        _gathering(date(2026, 6, 6), title='Outro dia')
        names = [g.title for g in gatherings_on_day(date(2026, 6, 5))]
    assert names == ['No dia']


# --------------------------------------------------------------------------- #
# Matriz do calendário (RF-102) — função pura (sem banco)
# --------------------------------------------------------------------------- #
def test_build_calendar_weeks_structure():
    """Semanas de 7 dias, domingo-first; transbordo `in_month=False`; hoje e evento."""
    today = date(2026, 6, 15)
    weeks = build_calendar_weeks(year=2026, month=6, event_days={5, 20}, today=today)

    # Toda semana tem 7 células; a 1ª célula é sempre um domingo.
    assert all(len(week) == 7 for week in weeks)
    first = weeks[0][0]
    assert date.fromisoformat(first['date']).weekday() == 6  # 6 = domingo

    flat = [cell for week in weeks for cell in week]
    by_iso = {cell['date']: cell for cell in flat}

    # Junho/2026 começa numa segunda => a 1ª célula (domingo) é 31/maio (transbordo).
    assert by_iso['2026-05-31']['in_month'] is False
    assert by_iso['2026-05-31']['has_event'] is False  # evento só conta no mês exibido

    d5 = by_iso['2026-06-05']
    assert d5['in_month'] is True
    assert d5['has_event'] is True
    assert d5['is_today'] is False
    assert by_iso['2026-06-15']['is_today'] is True
    assert by_iso['2026-06-10']['has_event'] is False
