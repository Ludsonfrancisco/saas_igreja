"""Modelo de importação na página (RF-033): botão "Baixar modelo" + CSV-modelo."""

import pytest
from django.db import connection
from django.test import Client

from apps.accounts.models import User

GOOD_PASSWORD = 'Senha@123'
IMPORT_URL = '/pessoas/importar/'
TEMPLATE_URL = '/pessoas/importar/modelo.csv'


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
def test_import_page_shows_template_link_and_example(tenant_client, church_a):
    tenant_client.force_login(_user(church_a, 'pastor@a.com', ['pastor']))
    html = tenant_client.get(IMPORT_URL).content.decode()
    assert TEMPLATE_URL in html  # botão "Baixar modelo"
    assert 'Maria Oliveira' in html  # exemplo inline
    assert 'Consentimento' in html  # rótulo pt-BR


@pytest.mark.django_db(transaction=True)
def test_template_csv_download(tenant_client, church_a):
    tenant_client.force_login(_user(church_a, 'secretary@a.com', ['secretary']))
    resp = tenant_client.get(TEMPLATE_URL)
    assert resp.status_code == 200
    assert resp['Content-Type'].startswith('text/csv')
    assert 'attachment' in resp['Content-Disposition']
    body = resp.content.decode('utf-8-sig')  # tolera o BOM
    assert body.splitlines()[0] == 'Nome,E-mail,Telefone,Situação,Consentimento'
    assert 'Membro' in body and 'Visitante' in body


@pytest.mark.django_db(transaction=True)
def test_template_download_role_barrier(tenant_client, church_a):
    """Mesma barreira da importação: Pastor/Secretário ok; Líder/Membro 403."""
    tenant_client.force_login(_user(church_a, 'leader@a.com', ['leader']))
    assert tenant_client.get(TEMPLATE_URL).status_code == 403
