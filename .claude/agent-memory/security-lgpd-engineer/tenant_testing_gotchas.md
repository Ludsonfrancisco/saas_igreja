---
name: tenant-testing-gotchas
description: django-tenants test gotchas (DDL/transaction=True, fixtures, tableless model stubs)
metadata:
  type: project
---

django-tenants test conventions discovered in apps/core/tests:

- Creating a `Church` triggers `auto_create_schema` = DDL with its own COMMIT. pytest's transactional rollback does NOT undo DDL, so any test using `church_a`/`church_b` fixtures MUST mark `@pytest.mark.django_db(transaction=True)`. Fixtures (conftest.py) DROP SCHEMA on teardown.
- conftest.py overrides `django_db_setup` to run `migrate_schemas --shared` so public tables exist in the test DB.
- To write rows into a tenant schema in tests: `with schema_context('tenant_a'): ...` (search_path switch). A row written in tenant_a is invisible from tenant_b (separate `core_auditlog` table per schema).
- Testing a signal receiver without a real migrated table: define a CONCRETE model subclass with `class Meta: managed = False, app_label='core'` in the TEST module (not in any app's models.py) — makemigrations won't see it, so no migration is generated, but `instance.pk` works (unlike an abstract model, whose `_meta.pk` is None and raises on `self.pk = ...`). Instantiate with `Model(id=1, name='x')`. Add a `__str__` or Ruff DJ008 fires.
- For middleware/sentry unit tests, no DB needed: use `types.SimpleNamespace` for fake request/user and plain dicts for Sentry events.

**Why:** these patterns avoid flaky reruns (leftover schemas) and avoid heavy migration plumbing to test signal logic.
**How to apply:** reuse for any future tenant-scoped model/signal tests. See [[audit-infrastructure]].
