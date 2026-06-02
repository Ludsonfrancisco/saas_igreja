---
name: provisioning-test-pattern
description: How to test django-tenants provisioning (create_church command + services) with DDL-safe teardown
metadata:
  type: project
---

Testing tenant provisioning (`apps/tenants/services.py`, `create_church` command) requires DDL-safe handling.

**Why:** `Church.save()` fires `auto_create_schema=True` → DDL + immediate COMMIT. The default transactional rollback of `@pytest.mark.django_db` does NOT undo DDL, so created schemas/rows leak across runs.

**How to apply:**
- Mark provisioning tests `@pytest.mark.django_db(transaction=True)`.
- Manual teardown in a `try/finally`: `DELETE` User/Domain/Church rows (in that FK order) + `DROP SCHEMA IF EXISTS "tenant_<slug>" CASCADE`.
- Use distinct slugs (svc, cmd, tradicional, ...) — never reuse athos/bethel/a/b (pre-existing tenants + fixtures in [[django-tenants-test-db]]).
- `ensure_public_tenant()` creates a Church(schema_name='public') ROW + Domain('localhost') ROW. The `public` schema already exists so no new schema is made. In teardown DELETE only those ROWS — NEVER `DROP SCHEMA public`.
- To assert a schema physically exists: query `information_schema.schemata`.
- Command tests: `call_command('create_church', slug, '--opt', val, stdout=StringIO())`; the dev-password WARNING goes to stdout (style.WARNING), assert on `out.getvalue()`.

Result: this brought Sprint 1 coverage 70% → 92.58%; services.py 100%, create_church.py 95%. Test files live at `apps/tenants/tests/test_services.py` and `test_create_church_command.py`.
