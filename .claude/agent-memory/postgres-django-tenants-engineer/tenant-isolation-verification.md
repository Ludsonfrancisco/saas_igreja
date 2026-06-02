---
name: tenant-isolation-verification
description: How to verify django-tenants concrete models migrate to tenant schemas and are absent from public
metadata:
  type: project
---

apps.core is in TENANT_APPS only (core/settings/base.py), so its concrete models
(AuditLog, SecurityLog) migrate into each tenant schema, never public. This is what
makes user_id IntegerField + tenant_id CharField valid (no cross-schema FK to User,
which lives in public). RN-014 / TENANT-04 / RISK-001.

**How to apply (migration + verification):**
- Migrate existing tenants: `uv run python manage.py migrate_schemas --tenant`
  (public = `migrate_schemas --shared`).
- Prove placement against dev DB (container `saas_igreja_db`, user `saas`, db `saas_igreja`):
  `SELECT table_schema, table_name FROM information_schema.tables WHERE table_name IN (...) ORDER BY 1,2;`
  Tables must appear under each tenant schema (tenant_athos, tenant_bethel) and NOT public.
  If a tenant-app table shows up in public, the app is wrongly in SHARED_APPS — stop and report.

**Isolation test pattern (verified working):**
- No-FK test: iterate `Model._meta.get_fields()`, assert none is a relation
  (`f.is_relation` is False for all) and `get_field('user_id').get_internal_type() == 'IntegerField'`.
- Physical scoping test: use `from django_tenants.utils import schema_context`; create a row
  inside `schema_context('tenant_a')`, then assert `Model.objects.count() == 0` inside
  `schema_context('tenant_b')`. Mark `@pytest.mark.django_db(transaction=True)` — auto_create_schema
  does DDL with its own commit, so transactional rollback won't undo it; fixtures DROP SCHEMA on teardown.
