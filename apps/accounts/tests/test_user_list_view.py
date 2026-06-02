"""Sprint 2 / Frente 3 — UserListView: escopo por igreja e barreira de papel.

A view aplica TenantRequiredMixin + PastorRequiredMixin e filtra
`User.objects.filter(church=request.tenant)`. Testamos:
- escopo por igreja: o Pastor da igreja A nao ve usuarios da igreja B (RISK-001);
- barreira de papel: nao-Pastor recebe 403;
- barreira de login: anonimo e redirecionado para o login.

Requests rodam no host do tenant_a (`a.testserver`) para que o TenantMiddleware
resolva o schema. `transaction=True` por causa do DDL de criar Church; o
search_path e restaurado para o public no teardown.
"""

import pytest
from django.db import connection
from django.test import Client

from apps.accounts.models import User

URL = '/configuracoes/usuarios/'
GOOD_PASSWORD = 'Senha@123'


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


@pytest.mark.django_db(transaction=True)
def test_list_users_scoped_by_church(tenant_client, church_a, church_b):
    """Pastor da igreja A so ve usuarios da A — nunca os da B (sem vazamento)."""
    pastor_a = _make_user(church_a, 'pastor@a.com', ['pastor'])
    _make_user(church_a, 'membro@a.com', ['member'])
    _make_user(church_b, 'membro@b.com', ['member'])

    tenant_client.force_login(pastor_a)
    resp = tenant_client.get(URL)
    assert resp.status_code == 200

    emails = {u.email for u in resp.context['users']}
    assert emails == {'pastor@a.com', 'membro@a.com'}
    assert 'membro@b.com' not in emails


@pytest.mark.django_db(transaction=True)
def test_list_users_denies_non_pastor(tenant_client, church_a):
    """Nao-Pastor (ex.: membro) recebe 403 na listagem (PastorRequiredMixin)."""
    member = _make_user(church_a, 'membro@a.com', ['member', 'leader'])
    tenant_client.force_login(member)
    resp = tenant_client.get(URL)
    assert resp.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_list_users_requires_login(tenant_client, church_a):
    """Anonimo nao acessa: TenantRequiredMixin (LoginRequired) redireciona.

    Regressao: LOGIN_URL='account_login' garante o redirect para a tela de login
    REAL do allauth (`/contas/login/`), nao o default do Django (`/accounts/login/`,
    rota inexistente neste projeto). Ver core/settings/base.py.
    """
    resp = tenant_client.get(URL)
    assert resp.status_code == 302
    # Aponta para o login do allauth (sob `contas/`), preservando o ?next — e
    # NUNCA para o `/accounts/login/` default do Django.
    assert resp.url.startswith('/contas/login/')
    assert '/accounts/login/' not in resp.url
    assert 'next=/configuracoes/usuarios/' in resp.url


@pytest.mark.django_db
def test_login_url_resolves_to_allauth_named_route():
    """LOGIN_URL e o nome `account_login` e resolve para `/contas/login/`.

    Trava o contrato do redirect de autenticacao em um unico ponto: se alguem
    mudar o prefixo `contas/` ou o LOGIN_URL, este teste sinaliza.
    """
    from django.conf import settings
    from django.urls import reverse

    assert settings.LOGIN_URL == 'account_login'
    assert reverse('account_login') == '/contas/login/'
