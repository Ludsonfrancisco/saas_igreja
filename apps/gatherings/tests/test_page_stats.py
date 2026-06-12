"""Analytics da tela de Encontros (RF-120) — cards + linha de presença mensal.

Valida `monthly_attendance_series` (presenças por mês) e `gatherings_page_stats`
(encontros/presenças/média/próximo). Tudo no schema do tenant.
"""

import datetime

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.gatherings import services
from apps.gatherings.models import Attendance, Gathering
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
GATHERINGS_URL = '/encontros/'


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _present(gathering, person):
    Attendance.objects.create(gathering=gathering, person=person, is_present=True)


@pytest.mark.django_db(transaction=True)
def test_gatherings_page_stats_month(church_a):
    today = datetime.date.today()
    with schema_context(church_a.schema_name):
        g = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=today, title='Culto'
        )
        a = Person.objects.create(name='A')
        b = Person.objects.create(name='B')
        _present(g, a)
        _present(g, b)
        stats = services.gatherings_page_stats(today=today)

    cards = {c['label']: c['value'] for c in stats['cards']}
    assert cards['Encontros no mês'] == 1
    assert cards['Presenças no mês'] == 2
    assert cards['Média por encontro'] == 2
    assert cards['Próximo encontro'] == today.strftime('%d/%m')


@pytest.mark.django_db(transaction=True)
def test_monthly_attendance_series_counts_by_month(church_a):
    today = datetime.date(2026, 6, 15)
    last_month = datetime.date(2026, 5, 10)
    with schema_context(church_a.schema_name):
        g_now = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=today, title='Junho'
        )
        g_prev = Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP, date=last_month, title='Maio'
        )
        p = Person.objects.create(name='P')
        q = Person.objects.create(name='Q')
        _present(g_now, p)
        _present(g_now, q)
        _present(g_prev, p)
        series = services.monthly_attendance_series(months=6, today=today)

    # 6 meses (Jan..Jun); Jun=2 presenças, Mai=1, demais 0.
    assert len(series['labels']) == 6
    assert len(series['values']) == 6
    assert series['values'][-1] == 2  # mês corrente (junho)
    assert series['values'][-2] == 1  # mês anterior (maio)
    assert sum(series['values']) == 3


@pytest.mark.django_db(transaction=True)
def test_gathering_list_renders_cards_and_chart(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        Gathering.objects.create(
            gathering_type=Gathering.Type.WORSHIP,
            date=datetime.date.today(),
            title='Culto',
        )
    tenant_client.force_login(pastor)
    resp = tenant_client.get(GATHERINGS_URL)
    html = resp.content.decode()
    assert 'Presença nos últimos 6 meses' in html
    assert 'attendance-trend-chart' in html
    assert 'Encontros no mês' in html
