"""Analytics da tela de Ministérios (RF-121) — cards + barra de GAP de voluntários.

Reusa `ministry_volunteer_gaps` (OD-029). Church-wide (§3.5). Tudo no tenant.
"""

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.ministries import services
from apps.ministries.models import Ministry
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
MIN_URL = '/ministerios/'


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
def test_ministries_page_stats_gap(church_a):
    with schema_context(church_a.schema_name):
        louvor = Ministry.objects.create(name='Louvor', volunteers_needed=4)
        Ministry.objects.create(name='Recepção', volunteers_needed=0)  # sem meta
        # Louvor tem 1 voluntário → GAP 3.
        p = Person.objects.create(name='Vol')
        p.ministries.add(louvor)
        stats = services.ministries_page_stats()

    cards = {c['label']: c['value'] for c in stats['cards']}
    assert cards['Ministérios'] == 2
    assert cards['Voluntários'] == 1
    assert cards['Faltam (GAP)'] == 3
    assert cards['Sem meta definida'] == 1
    # Gráfico: GAP por ministério (ordem por nome → Louvor, Recepção).
    assert stats['chart']['labels'] == ['Louvor', 'Recepção']
    assert stats['chart']['values'] == [3, 0]


@pytest.mark.django_db(transaction=True)
def test_ministry_list_renders_cards_and_chart(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        Ministry.objects.create(name='Louvor', volunteers_needed=2)
    tenant_client.force_login(pastor)
    resp = tenant_client.get(MIN_URL)
    html = resp.content.decode()
    assert 'Saúde do Ministério' in html
    assert 'ministry-gap-chart' in html
    assert 'Faltam (GAP)' in html
