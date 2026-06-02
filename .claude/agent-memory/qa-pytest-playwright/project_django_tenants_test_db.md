---
name: django-tenants-test-db
description: How the pytest suite provisions a migrated public schema under django-tenants, and the transaction=True rule for tenant-creating tests
metadata:
  type: project
---

Root `conftest.py` overrides session fixture `django_db_setup` to chain the pytest-django one then run `call_command('migrate_schemas', '--shared')`, ensuring SHARED_APPS (User/Church/Domain/Invite, accounts+tenants) materialize in the `public` schema of the test DB.

**Why:** backend is `django_tenants.postgresql_backend` with `TenantSyncRouter`, which splits SHARED vs TENANT apps; the default `migrate` is not the canonical way to provision public.

**How to apply:**
- Any test that creates a `Church` triggers `TenantMixin.save` → `auto_create_schema` → `create_schema` (DDL with its own COMMIT, runs schema-clone migrations outside the test transaction). Such tests MUST use `@pytest.mark.django_db(transaction=True)` — plain `django_db` rollback does NOT undo DDL.
- `church_a`/`church_b` fixtures (in root conftest) yield then `DROP SCHEMA IF EXISTS "tenant_x" CASCADE` in teardown to keep reruns clean.
- `Invite` (and any model FK-bound to Church) cannot be created without a Church, so even "model-only" tests like BaseModel timestamps need `transaction=True`. Don't fight this.
- Middleware test pattern that worked: `TenantMiddleware(get_response=...)` + `RequestFactory().get('/', HTTP_HOST='a.testserver')` + `process_request(request)`, then assert `connection.schema_name == 'tenant_a'`. Reset with `connection.set_schema_to_public()` in a `finally`. See [[debug-toolbar-tests]].
