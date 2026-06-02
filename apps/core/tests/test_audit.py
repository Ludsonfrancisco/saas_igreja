"""Sprint 2 — AuditLog / SecurityLog: isolamento por tenant (RN-014 / TENANT-04).

Dois invariantes do §5.9.1 (RISK-001):

1. NENHUM dos models tem FK/O2O cross-schema (em especial para User, que vive no
   `public`). O vinculo ao usuario e um `user_id IntegerField` simples. Isso e o
   que torna valido manter esses logs no schema do tenant sem FK cross-schema.
2. As linhas vivem fisicamente apenas no schema do tenant que as criou: uma linha
   gravada em `tenant_a` NAO e visivel a partir de `tenant_b` (cada schema tem sua
   propria tabela `core_auditlog`).

Os testes que criam Church usam `transaction=True` porque `auto_create_schema`
faz DDL com commit proprio (o rollback transacional do pytest nao desfaz DDL); as
fixtures church_a/church_b fazem DROP SCHEMA no teardown.
"""

import pytest
from django.db.models import ForeignKey, ManyToManyField, OneToOneField
from django_tenants.utils import schema_context

from apps.core.models import AuditLog, SecurityLog


@pytest.mark.parametrize('model', [AuditLog, SecurityLog])
def test_auditlog_no_cross_schema_fk(model):
    """Nenhum campo relacional (FK/O2O/M2M) — user_id e IntegerField puro.

    TENANT-04 / RN-014: logs vivem no tenant; qualquer FK para User (model do
    `public`) seria uma FK cross-schema, proibida.
    """
    relation_types = (ForeignKey, OneToOneField, ManyToManyField)
    relations = [
        f
        for f in model._meta.get_fields()
        if isinstance(f, relation_types) or f.is_relation
    ]
    assert relations == [], (
        f'{model.__name__} nao pode ter campos relacionais '
        f'(cross-schema FK proibida): {relations}'
    )

    user_id_field = model._meta.get_field('user_id')
    assert user_id_field.get_internal_type() == 'IntegerField'


@pytest.mark.django_db(transaction=True)
def test_auditlog_scoped_by_tenant_id(church_a, church_b):
    """Uma linha criada em tenant_a nao e visivel a partir de tenant_b.

    Isolamento fisico: cada schema tem sua propria tabela core_auditlog. O
    `schema_context` troca o search_path; a contagem em tenant_b nao enxerga a
    linha de tenant_a.
    """
    with schema_context('tenant_a'):
        AuditLog.objects.create(
            action='create',
            model_name='Person',
            object_id='1',
            tenant_id='tenant_a',
            user_id=1,
        )
        assert AuditLog.objects.filter(tenant_id='tenant_a').count() == 1

    with schema_context('tenant_b'):
        assert AuditLog.objects.count() == 0
