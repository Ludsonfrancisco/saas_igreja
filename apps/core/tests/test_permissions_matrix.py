"""Sprint 2 / Frente 7 — Gate de permissões por papel (P-ARQ-08 / ACCESS_MATRIX).

Versão INICIAL do `test_permissions_matrix` (TEST_STRATEGY §6.2): uma linha por
célula (papel × view) das views autenticadas JÁ EXISTENTES na Sprint 2. Cobre o
contrato Pastor vs Leader vs Member:

- views de gestão (usuários, convites) exigem `pastor` (PastorRequiredMixin) —
  Leader e Member recebem 403;
- a página "Segurança da conta" é login-only — qualquer papel autenticado entra.

A barreira de papel roda no `dispatch` (antes do método HTTP), então um GET basta
para exercitar a célula. Conforme novas views/ações nascem (Sprint 3+: create,
anonymize, etc.), acrescente as células a `PERMISSION_CASES`.

`transaction=True` por causa do DDL de criar Church; search_path restaurado no
teardown.
"""

import pytest
from django.db import connection
from django.test import Client

from apps.accounts.models import User

GOOD_PASSWORD = 'Senha@123'

USER_LIST = '/configuracoes/usuarios/'
INVITE_LIST = '/configuracoes/convites/'
INVITE_CREATE = '/configuracoes/convites/novo/'
ACCOUNT_SECURITY = '/contas/seguranca/'

# (papel, url, status_esperado) — GET. 200 = liberado, 403 = negado pelo papel.
PERMISSION_CASES = [
    # Views só-Pastor: Leader e Member negados.
    ('pastor', USER_LIST, 200),
    ('leader', USER_LIST, 403),
    ('member', USER_LIST, 403),
    ('pastor', INVITE_LIST, 200),
    ('leader', INVITE_LIST, 403),
    ('member', INVITE_LIST, 403),
    ('pastor', INVITE_CREATE, 200),
    ('leader', INVITE_CREATE, 403),
    ('member', INVITE_CREATE, 403),
    # Segurança da conta: login-only, qualquer papel entra.
    ('pastor', ACCOUNT_SECURITY, 200),
    ('leader', ACCOUNT_SECURITY, 200),
    ('member', ACCOUNT_SECURITY, 200),
]


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('role,url,expected', PERMISSION_CASES)
def test_permissions_matrix(tenant_client, church_a, role, url, expected):
    """Cada célula (papel × view): o status confirma a barreira de papel."""
    user = User.objects.create_user(
        email=f'{role}@a.com', password=GOOD_PASSWORD, roles=[role], church=church_a
    )
    tenant_client.force_login(user)

    resp = tenant_client.get(url)
    assert resp.status_code == expected
