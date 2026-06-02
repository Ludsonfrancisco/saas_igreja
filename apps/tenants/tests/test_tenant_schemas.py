"""Sprint 1 — isolamento fisico de schema por tenant (RN-001 / TENANT-01).

Cada igreja recebe um schema PostgreSQL distinto e fisicamente criado via
`auto_create_schema=True`. Cobre o teste minimo
`test_two_churches_distinct_schemas` (SPRINTS Sprint 1).
"""

import pytest
from django.db import connection


def _schema_exists(schema_name):
    """True se o schema existe em information_schema.schemata."""
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT 1 FROM information_schema.schemata WHERE schema_name = %s',
            [schema_name],
        )
        return cursor.fetchone() is not None


@pytest.mark.django_db(transaction=True)
def test_two_churches_distinct_schemas(church_a, church_b):
    # Cada tenant tem nome de schema proprio e distinto.
    assert church_a.schema_name == 'tenant_a'
    assert church_b.schema_name == 'tenant_b'
    assert church_a.schema_name != church_b.schema_name

    # Ambos os schemas foram fisicamente criados (auto_create_schema).
    assert _schema_exists('tenant_a')
    assert _schema_exists('tenant_b')
