"""Sprint 2 — record_audit / log_security_event: gravacao e guarda de schema.

Cobre o caminho feliz (grava no schema do tenant com tenant_id correto) e a
guarda de schema public (RN-014 / TENANT-04): AuditLog/SecurityLog so existem em
schemas de tenant, entao chamadas no public retornam None sem gravar nada.

Usa church_a com `transaction=True` porque criar Church dispara auto_create_schema
(DDL com commit proprio); a fixture faz DROP SCHEMA no teardown.
"""

import pytest
from django_tenants.utils import schema_context

from apps.core.audit import log_security_event, record_audit
from apps.core.models import AuditLog, SecurityLog


@pytest.mark.django_db(transaction=True)
def test_record_audit_creates_auditlog_in_tenant(church_a):
    with schema_context('tenant_a'):
        entry = record_audit(
            action='create',
            model_name='Person',
            object_id='1',
            object_repr='Maria',
            user_id=5,
            ip_address='192.0.2.10',
        )

        assert entry is not None
        assert entry.tenant_id == 'tenant_a'
        assert entry.action == 'create'
        assert entry.model_name == 'Person'
        assert entry.object_id == '1'
        assert entry.user_id == 5
        assert entry.ip_address == '192.0.2.10'
        assert AuditLog.objects.filter(tenant_id='tenant_a').count() == 1


@pytest.mark.django_db(transaction=True)
def test_record_audit_in_public_schema_returns_none_and_writes_nothing(church_a):
    # No schema public nao ha tabela core_auditlog: a guarda devolve None e nao
    # tenta gravar (nem estoura relation-does-not-exist).
    result = record_audit(action='create', model_name='User', object_id='1')

    assert result is None
    with schema_context('tenant_a'):
        assert AuditLog.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_log_security_event_creates_securitylog_in_tenant(church_a):
    with schema_context('tenant_a'):
        entry = log_security_event(
            event_type='role_change',
            user_id=9,
            payload={'roles_added': ['leader']},
            ip_address='192.0.2.20',
        )

        assert entry is not None
        assert entry.tenant_id == 'tenant_a'
        assert entry.event_type == 'role_change'
        assert entry.payload == {'roles_added': ['leader']}
        assert entry.user_id == 9
        assert SecurityLog.objects.filter(tenant_id='tenant_a').count() == 1


@pytest.mark.django_db(transaction=True)
def test_log_security_event_in_public_schema_returns_none(church_a):
    result = log_security_event(event_type='login_success', user_id=1)

    assert result is None
    with schema_context('tenant_a'):
        assert SecurityLog.objects.count() == 0
