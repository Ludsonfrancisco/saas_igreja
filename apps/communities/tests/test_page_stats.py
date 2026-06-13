"""Analytics da tela de Comunidades (RF-119) — cards + frequência por célula.

Valida os KPIs (células, frequência média, pendentes, membros), o escopo por papel
(Líder só a sua célula) e o gráfico. Tudo no schema do tenant.
"""

import datetime

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities import services
from apps.communities.models import Community
from apps.gatherings import services as gathering_services
from apps.gatherings.models import Gathering
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
COMM_URL = '/comunidades/'
DATE = datetime.date(2026, 6, 14)


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _launched_session(cell, present_people):
    """Cria um encontro de Comunidade confirmado com presença marcada."""
    g = Gathering.objects.create(
        gathering_type=Gathering.Type.COMMUNITY, community=cell, date=DATE
    )
    gathering_services.launch_attendance_session(
        gathering=g,
        present_person_ids=[p.pk for p in present_people],
        visitor_names=[],
        note='',
        confirmed_by_id=1,
    )
    return g


@pytest.mark.django_db(transaction=True)
def test_communities_page_stats(church_a):
    with schema_context(church_a.schema_name):
        cell = Community.objects.create(name='Célula 1')
        a = Person.objects.create(name='A', community=cell)
        b = Person.objects.create(name='B', community=cell)
        _launched_session(cell, [a, b])  # sessão confirmada (2 presentes)

        communities = list(Community.objects.all())
        freqs = gathering_services.cell_frequencies(communities)
        stats = services.communities_page_stats(communities=communities, freqs=freqs)

    cards = {c['label']: c['value'] for c in stats['cards']}
    assert cards['Células'] == 1
    assert cards['Membros nas células'] == 2
    assert cards['Frequência média'] == 2  # média de presentes da única sessão
    assert cards['Lançamento pendente'] == 0  # a única reunião foi lançada
    assert stats['chart']['labels'] == ['Célula 1']
    assert stats['chart']['values'] == [2]


@pytest.mark.django_db(transaction=True)
def test_communities_pending_counts_unlaunched(church_a):
    with schema_context(church_a.schema_name):
        cell = Community.objects.create(name='Pendente')
        # Encontro de Comunidade SEM sessão confirmada → pendente.
        Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY, community=cell, date=DATE
        )
        communities = list(Community.objects.all())
        freqs = gathering_services.cell_frequencies(communities)
        stats = services.communities_page_stats(communities=communities, freqs=freqs)
    cards = {c['label']: c['value'] for c in stats['cards']}
    assert cards['Lançamento pendente'] == 1


@pytest.mark.django_db(transaction=True)
def test_communities_stats_scoped_to_leader(tenant_client, church_a):
    """RF-119/RF-106: o Líder só vê os números da(s) célula(s) que lidera."""
    leader = _user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        mine = Community.objects.create(name='Minha')
        mine.leaders.add(Person.objects.create(name='Lider', user_id=leader.id))
        Community.objects.create(name='Outra')  # fora do escopo
    tenant_client.force_login(leader)
    resp = tenant_client.get(COMM_URL)
    assert resp.status_code == 200
    cards = {c['label']: c['value'] for c in resp.context['stats']['cards']}
    assert cards['Células'] == 1  # só a célula do líder


@pytest.mark.django_db(transaction=True)
def test_community_list_renders_cards_and_chart(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        Community.objects.create(name='Célula X')
    tenant_client.force_login(pastor)
    resp = tenant_client.get(COMM_URL)
    html = resp.content.decode()
    # Título do gráfico usa o rótulo configurável (F2/OD-032). Sem customização,
    # o default é "Comunidade" → "Frequência por comunidade".
    assert 'Frequência por comunidade' in html
    assert 'cell-freq-chart' in html
    assert 'Lançamento pendente' in html
