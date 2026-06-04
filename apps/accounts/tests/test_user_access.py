"""Sprint 3 / Frente 3 (Bloco 4b) — tela de Gestão de Acessos (UserList + UserAccess).

Pastor ou Secretário concede funções (roles) e ativa/desativa um usuário da igreja.
As travas (RISK-015) e RN-004 são do service layer; aqui validamos o gate de papel,
o escopo por igreja, e que as travas SURFAÇAM no fluxo HTTP.

Requests no host do tenant (`a.testserver`); User é público, mas filtrado por
`church`. `transaction=True` por causa do DDL de criar Church.
"""

import pytest
from django.db import connection
from django.test import Client

from apps.accounts.models import User

GOOD_PASSWORD = 'Senha@123'
LIST_URL = '/configuracoes/usuarios/'


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
    [(['pastor'], 200), (['secretary'], 200), (['leader'], 403), (['member'], 403)],
)
def test_user_list_access_barrier(tenant_client, church_a, roles, expected):
    user = _user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    assert tenant_client.get(LIST_URL).status_code == expected


@pytest.mark.django_db(transaction=True)
def test_pastor_changes_roles_via_view(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    target = _user(church_a, 'alvo@a.com', ['member'])
    tenant_client.force_login(pastor)

    resp = tenant_client.post(
        f'{LIST_URL}{target.pk}/acesso/',
        {'roles': ['leader', 'treasurer'], 'is_active': 'on'},
    )
    assert resp.status_code == 302
    target.refresh_from_db()
    assert set(target.roles) == {'leader', 'treasurer'}


@pytest.mark.django_db(transaction=True)
def test_secretary_can_grant_non_pastor_roles(tenant_client, church_a):
    secretary = _user(church_a, 'sec@a.com', ['secretary'])
    _user(church_a, 'pastor@a.com', ['pastor'])
    target = _user(church_a, 'alvo@a.com', ['member'])
    tenant_client.force_login(secretary)

    resp = tenant_client.post(
        f'{LIST_URL}{target.pk}/acesso/',
        {'roles': ['leader'], 'is_active': 'on'},
    )
    assert resp.status_code == 302
    target.refresh_from_db()
    assert set(target.roles) == {'leader'}


@pytest.mark.django_db(transaction=True)
def test_secretary_cannot_grant_pastor_via_view(tenant_client, church_a):
    """A trava do service SURFAÇA no HTTP: 200 (form com erro), nada muda."""
    secretary = _user(church_a, 'sec@a.com', ['secretary'])
    _user(church_a, 'pastor@a.com', ['pastor'])  # mantém um Pastor
    target = _user(church_a, 'alvo@a.com', ['member'])
    tenant_client.force_login(secretary)

    resp = tenant_client.post(
        f'{LIST_URL}{target.pk}/acesso/',
        {'roles': ['pastor'], 'is_active': 'on'},
    )
    assert resp.status_code == 200
    target.refresh_from_db()
    assert 'pastor' not in target.roles


@pytest.mark.django_db(transaction=True)
def test_deactivate_via_view(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    target = _user(church_a, 'alvo@a.com', ['member'])
    tenant_client.force_login(pastor)

    # is_active ausente -> desativa (roles inalteradas).
    resp = tenant_client.post(f'{LIST_URL}{target.pk}/acesso/', {'roles': ['member']})
    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.is_active is False


@pytest.mark.django_db(transaction=True)
def test_reactivate_via_view(tenant_client, church_a):
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    target = _user(church_a, 'alvo@a.com', ['member'])
    target.is_active = False
    target.save(update_fields=['is_active'])
    tenant_client.force_login(pastor)

    # is_active marcado -> reativa.
    resp = tenant_client.post(
        f'{LIST_URL}{target.pk}/acesso/', {'roles': ['member'], 'is_active': 'on'}
    )
    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.is_active is True


@pytest.mark.django_db(transaction=True)
def test_user_access_member_forbidden(tenant_client, church_a):
    member = _user(church_a, 'membro@a.com', ['member'])
    target = _user(church_a, 'alvo@a.com', ['member'])
    tenant_client.force_login(member)
    assert tenant_client.get(f'{LIST_URL}{target.pk}/acesso/').status_code == 403


@pytest.mark.django_db(transaction=True)
def test_user_access_cross_tenant_404(tenant_client, church_a, church_b):
    """Usuário de outra igreja não é gerenciável (escopo por `church`) -> 404."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    other = _user(church_b, 'b@b.com', ['member'])
    tenant_client.force_login(pastor)
    assert tenant_client.get(f'{LIST_URL}{other.pk}/acesso/').status_code == 404
