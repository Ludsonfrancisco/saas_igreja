"""Sprint 2 — signals de auditoria automatica (P-ARQ-06).

Approach (judgment call): testamos os RECEIVERS diretamente, sem materializar um
model concreto de teste no banco. Sob django-tenants, criar uma tabela so para o
teste exigiria migration plumbing por schema (auto_create_schema roda as
migracoes de TENANT_APPS no momento da criacao do tenant; um model declarado so
no teste nao estaria nessas migracoes). Em vez disso:

- Definimos um `_AuditedDummy(AuditLogMixin)` ABSTRATO so para o `isinstance`
  (sem tabela, sem migracao) e instanciamos com pk/atributos setados a mao.
- Chamamos `audit_on_save` / `audit_on_delete` (as funcoes reais conectadas no
  ready()) e verificamos que uma linha AuditLog resulta no schema do tenant, com
  a action correta (create/update/delete).
- Verificamos tambem o filtro: uma instancia que NAO herda de AuditLogMixin nao
  gera AuditLog (sem auditar models nao-marcados, nem recursao em AuditLog).

Isso exercita o caminho real do signal (filtro de tipo + derivacao de
model_name/object_id + record_audit) sem hack de migracao.
"""

import pytest
from django.db import models
from django_tenants.utils import schema_context

from apps.core.models import AuditLog, AuditLogMixin
from apps.core.signals import audit_on_delete, audit_on_save


class _AuditedDummy(AuditLogMixin):
    """Subclasse CONCRETA de AuditLogMixin, mas managed=False -> sem migracao.

    Concreta (nao abstrata) para que `instance.pk` exista e `record_audit` derive
    object_id/object_repr do instance. `managed=False` + definicao apenas no
    modulo de teste fazem com que nenhuma migracao seja gerada para ela
    (makemigrations so olha os apps em INSTALLED_APPS/models.py). Nao gravamos a
    instancia no banco; chamamos os receivers a mao.
    """

    name = models.CharField(max_length=20)

    class Meta:
        app_label = 'core'
        managed = False

    def __str__(self):
        return f'dummy-{self.pk}'


class _NotAudited(models.Model):
    """Model fora da hierarquia de AuditLogMixin (nao deve ser auditado)."""

    name = models.CharField(max_length=20)

    class Meta:
        app_label = 'core'
        managed = False

    def __str__(self):
        return f'not-audited-{self.pk}'


@pytest.mark.django_db(transaction=True)
def test_signal_audits_create_and_update_and_delete(church_a):
    with schema_context('tenant_a'):
        dummy = _AuditedDummy(id=1, name='x')
        # created=True -> action='create'
        audit_on_save(sender=_AuditedDummy, instance=dummy, created=True)
        # created=False -> action='update'
        audit_on_save(sender=_AuditedDummy, instance=dummy, created=False)
        # delete -> action='delete'
        audit_on_delete(sender=_AuditedDummy, instance=dummy)

        rows = AuditLog.objects.filter(tenant_id='tenant_a', model_name='_AuditedDummy')
        actions = sorted(rows.values_list('action', flat=True))
        assert actions == ['create', 'delete', 'update']
        # object_id/object_repr derivados do instance.
        create_row = rows.get(action='create')
        assert create_row.object_id == '1'
        assert create_row.object_repr == 'dummy-1'


@pytest.mark.django_db(transaction=True)
def test_signal_ignores_non_auditlogmixin_instances(church_a):
    with schema_context('tenant_a'):
        other = _NotAudited(id=1, name='x')
        audit_on_save(sender=_NotAudited, instance=other, created=True)
        audit_on_delete(sender=_NotAudited, instance=other)

        assert AuditLog.objects.count() == 0
