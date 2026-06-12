"""Campos do design Athos v3 em Comunidades (RF-122/123): tipo + lotação/ocupação."""

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.communities.models import Community
from apps.gatherings import services as gathering_services
from apps.gatherings.models import Gathering
from apps.people.models import Person

GOOD_PASSWORD = 'Senha@123'
COMM_URL = '/comunidades/'


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


@pytest.mark.django_db(transaction=True)
def test_community_category_field(church_a):
    with schema_context(church_a.schema_name):
        c = Community.objects.create(name='Jovens', category=Community.Category.YOUTH)
        assert c.category == 'youth'
        # default é Mista.
        assert Community.objects.create(name='X').category == 'mixed'


@pytest.mark.django_db(transaction=True)
def test_community_occupancy_and_freq_pct(tenant_client, church_a):
    """RF-123: card recebe members_count + % ocupação + % frequência."""
    pastor = User.objects.create_user(
        email='pastor@a.com', password=GOOD_PASSWORD, roles=['pastor'], church=church_a
    )
    with schema_context(church_a.schema_name):
        cell = Community.objects.create(name='Célula', max_members=10)
        a = Person.objects.create(name='A', community=cell)
        Person.objects.create(name='B', community=cell)  # 2º membro
        # Uma sessão confirmada com 1 presente → avg_present=1; freq% = 1/2 = 50%.
        g = Gathering.objects.create(
            gathering_type=Gathering.Type.COMMUNITY, community=cell, date='2026-06-14'
        )
        gathering_services.launch_attendance_session(
            gathering=g, present_person_ids=[a.pk], confirmed_by_id=1
        )
    tenant_client.force_login(pastor)
    resp = tenant_client.get(COMM_URL)
    community = resp.context['communities'][0]
    assert community.members_count == 2
    assert community.occupancy_pct == 20  # 2 de 10
    assert community.freq_pct == 50  # 1 presente / 2 membros
