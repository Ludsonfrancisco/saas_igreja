"""Configurações da igreja — rótulos configuráveis (F2 / OD-032 / RF-126-127).

Pastor edita os termos; a UI (sidebar/títulos) passa a exibir o termo escolhido.
"""

import pytest
from django.db import connection
from django.test import Client

from apps.accounts.models import User

GOOD_PASSWORD = 'Senha@123'
SETTINGS_URL = '/configuracoes/igreja/'


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
@pytest.mark.parametrize(
    'roles,expected',
    [(['pastor'], 200), (['secretary'], 403), (['leader'], 403), (['member'], 403)],
)
def test_church_settings_pastor_only(tenant_client, church_a, roles, expected):
    tenant_client.force_login(_user(church_a, f'{roles[0]}@a.com', roles))
    assert tenant_client.get(SETTINGS_URL).status_code == expected


@pytest.mark.django_db(transaction=True)
def test_pastor_edits_labels_and_ui_reflects(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    resp = tenant_client.post(
        SETTINGS_URL,
        {
            'leader_title': 'Pastor',
            'community_label': 'Célula',
            'community_label_plural': 'Células',
            'ministry_label': 'Departamento',
            'ministry_label_plural': 'Departamentos',
        },
    )
    assert resp.status_code == 302
    church_a.refresh_from_db()
    assert church_a.community_label == 'Célula'
    assert church_a.ministry_label_plural == 'Departamentos'

    # A sidebar passa a exibir os termos escolhidos (context processor `terms`).
    html = tenant_client.get('/pessoas/').content.decode()
    assert 'Células' in html
    assert 'Departamentos' in html


@pytest.mark.django_db(transaction=True)
def test_default_terms_are_standard(tenant_client, church_a):
    """Sem customização, a UI mantém Comunidades/Ministérios (defaults)."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)
    html = tenant_client.get('/comunidades/').content.decode()
    assert 'Comunidades' in html
