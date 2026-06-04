"""Fixtures globais da suite (TEST_STRATEGY §5).

Sprint 1: apenas o subconjunto de fixtures que referencia models JA existentes
(User, Church, Domain). Fixtures de Person/Community/etc. (Sprint 3+) NAO entram
aqui — criar fixtures para models inexistentes quebraria a coleta (TAP-08 e o
principio de so testar o que tem requisito vinculado).

Particularidade django-tenants no banco de teste
-------------------------------------------------
O backend `django_tenants.postgresql_backend` + `TenantSyncRouter` separam
SHARED_APPS (schema `public`) de TENANT_APPS (schema de cada tenant). Para que
as tabelas publicas (User/Church/Domain/Invite/...) existam no banco de teste,
o schema public precisa ser migrado com `migrate_schemas --shared`. Por isso
`django_db_setup` e sobrescrito abaixo: o `migrate` padrao do pytest-django,
sob o router de tenants, nao e a forma canonica de provisionar o public.

Fixtures que criam uma Church disparam `auto_create_schema=True` (DDL + COMMIT
imediato). Testes que as usam DEVEM marcar `@pytest.mark.django_db(transaction=True)`
— o rollback transacional padrao nao desfaz DDL. O teardown de `church_a`/
`church_b` derruba o schema criado (DROP SCHEMA ... CASCADE) para manter reruns
limpos.
"""

import pytest
from django.core.management import call_command
from django.db import connection


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Garante o schema public migrado (shared apps) no banco de teste.

    pytest-django ja cria o banco de teste e roda as migracoes via a fixture
    `django_db_setup` original (encadeada aqui como argumento). Sob o backend
    django-tenants, reforcamos com `migrate_schemas --shared` para assegurar
    que todas as SHARED_APPS estejam materializadas no `public` antes de
    qualquer teste tocar User/Church/Domain.
    """
    with django_db_blocker.unblock():
        call_command('migrate_schemas', '--shared', verbosity=0)
    yield


def _drop_schema(schema_name):
    """Remove fisicamente um schema de tenant (teardown de DDL nao-transacional)."""
    with connection.cursor() as cursor:
        cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')


@pytest.fixture
def public_user(db):
    """User no schema public (sem church)."""
    from apps.accounts.models import User

    return User.objects.create_user(
        email='admin@platform.com',
        password='Test1234!',
        roles=['pastor'],
    )


@pytest.fixture
def church_a(db):
    """Tenant A + seu Domain. Dispara auto_create_schema (DDL)."""
    from apps.tenants.models import Church, Domain

    church = Church.objects.create(name='Igreja A', slug='a', schema_name='tenant_a')
    Domain.objects.create(domain='a.testserver', tenant=church, is_primary=True)
    yield church
    _drop_schema('tenant_a')


@pytest.fixture
def church_b(db):
    """Tenant B + seu Domain. Para testes de isolamento. Dispara DDL."""
    from apps.tenants.models import Church, Domain

    church = Church.objects.create(name='Igreja B', slug='b', schema_name='tenant_b')
    Domain.objects.create(domain='b.testserver', tenant=church, is_primary=True)
    yield church
    _drop_schema('tenant_b')


@pytest.fixture
def in_tenant_a(church_a):
    """Executa o corpo do teste DENTRO do schema do tenant A.

    Models de TENANT_APPS (Person/Community/Ministry/...) só existem no schema do
    tenant; testes de ORM puro precisam operar lá. O `schema_context` aponta o
    search_path para `tenant_a` durante o teste e o restaura para o public no fim.
    Usar com `@pytest.mark.django_db(transaction=True)` (DDL de criar Church).
    """
    from django_tenants.utils import schema_context

    with schema_context(church_a.schema_name):
        yield church_a
    connection.set_schema_to_public()


@pytest.fixture
def pastor_a(db, church_a):
    """Pastor do tenant A (User publico, FK simples para church_a)."""
    from apps.accounts.models import User

    return User.objects.create_user(
        email='pastor@a.com',
        password='Test1234!',
        roles=['pastor'],
        church=church_a,
    )


@pytest.fixture
def pastor_b(db, church_b):
    """Pastor do tenant B (User publico, FK simples para church_b)."""
    from apps.accounts.models import User

    return User.objects.create_user(
        email='pastor@b.com',
        password='Test1234!',
        roles=['pastor'],
        church=church_b,
    )
