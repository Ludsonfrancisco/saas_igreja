"""Analytics da tela de Pessoas (RF-118) — cards + gráfico de situação, escopados.

`people_page_stats` recebe o queryset já escopado; aqui validamos os números e o
escopo por papel (Líder só conta o seu vínculo). Tudo no schema do tenant.
"""

import datetime

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.people import services
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
PEOPLE_URL = '/pessoas/'


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


@pytest.mark.django_db(transaction=True)
def test_people_page_stats_counts(church_a):
    with schema_context(church_a.schema_name):
        Person.objects.create(name='M1', status=Person.Status.MEMBER)
        Person.objects.create(name='M2', status=Person.Status.MEMBER)
        Person.objects.create(name='V1', status=Person.Status.VISITOR)
        # Anonimizada NÃO entra (base já exclui anonymized_at).
        base = Person.objects.filter(anonymized_at__isnull=True)
        stats = services.people_page_stats(person_qs=base)

    cards = {c['label']: c['value'] for c in stats['cards']}
    assert cards['Pessoas'] == 3
    assert cards['Membros'] == 2
    assert cards['Visitantes'] == 1
    # Gráfico: Membro (2) antes de Visitante (1), ordem de _STATUS_ORDER.
    assert stats['chart']['labels'] == ['Membro', 'Visitante']
    assert stats['chart']['values'] == [2, 1]


@pytest.mark.django_db(transaction=True)
def test_people_birthdays_this_month(church_a):
    today = datetime.date.today()
    this_month = today.replace(day=10)
    other_month = (today.replace(day=10) + datetime.timedelta(days=60)).replace(day=10)
    with schema_context(church_a.schema_name):
        Person.objects.create(name='Aniver', birth_date=this_month.replace(year=1990))
        Person.objects.create(name='Outro', birth_date=other_month.replace(year=1990))
        base = Person.objects.filter(anonymized_at__isnull=True)
        stats = services.people_page_stats(person_qs=base)
    cards = {c['label']: c['value'] for c in stats['cards']}
    assert cards['Aniversariantes do mês'] == 1


@pytest.mark.django_db(transaction=True)
def test_people_stats_scoped_to_leader(tenant_client, church_a):
    """RF-118 escopado: o Líder só conta as pessoas da sua comunidade."""
    leader = _user(church_a, 'leader@a.com', ['leader'])
    with schema_context(church_a.schema_name):
        cell = Community.objects.create(name='Célula do Líder')
        cell.leaders.add(Person.objects.create(name='Lider P', user_id=leader.id))
        Person.objects.create(
            name='Da Célula', status=Person.Status.MEMBER, community=cell
        )
        Person.objects.create(name='De Fora', status=Person.Status.MEMBER)  # outra
    tenant_client.force_login(leader)
    resp = tenant_client.get(PEOPLE_URL)
    assert resp.status_code == 200
    cards = {c['label']: c['value'] for c in resp.context['stats']['cards']}
    # Só "Da Célula" (community=cell do líder); "De Fora" e o próprio líder
    # (community=None) não entram no escopo `community__leaders__user_id`.
    assert cards['Pessoas'] == 1


@pytest.mark.django_db(transaction=True)
def test_people_list_renders_cards_and_chart(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        Person.objects.create(name='Alguem', status=Person.Status.MEMBER)
    tenant_client.force_login(pastor)
    resp = tenant_client.get(PEOPLE_URL)
    html = resp.content.decode()
    assert 'Pessoas por situação' in html
    assert 'people-status-chart' in html
    assert 'Aniversariantes do mês' in html
