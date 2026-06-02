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
- Auth-flow tests (Sprint 2 Front 2) that drive real allauth views must hit a tenant host so SecurityLog persists: `Client(HTTP_HOST='a.testserver')` (the church_a Domain). The TenantMiddleware leaves `connection`'s search_path on the tenant AFTER the request — the test client does NOT reset it. So the client fixture teardown MUST call `connection.set_schema_to_public()`, else the next test's `Church.objects.create` raises "Can't create tenant outside the public schema". Query SecurityLog via `with schema_context('tenant_a')` after resetting to public.
- axes state isolation: ALL axes tables (AccessAttempt, AccessAttemptExpiration, AccessFailureLog, AccessLog) live in PUBLIC and are NOT rolled back in transaction=True tests. Purge all four in setup+teardown AND give each lockout test a UNIQUE (email, REMOTE_ADDR) pair — residual expiration/failure rows for a reused username silently suppress new lockouts (attempts stop recording, no 429). axes lockout response is 429.
- Password-reset-completed E2E: don't forge allauth's reset URL (its own uidb36+key format, not Django's token). POST the email to /contas/password/reset/, then regex the reset URL out of `django.core.mail.outbox[0].body` (console backend), GET it (redirects to set-password), then POST the new password.
- Token-expiry test: subclass PasswordResetTokenGenerator and override `_now()` returning a NAIVE datetime (Django's internal baseline `datetime(2001,1,1)` is naive — an aware datetime raises "can't subtract offset-naive and offset-aware").

**Why:** these patterns avoid flaky reruns (leftover schemas) and avoid heavy migration plumbing to test signal logic.
**How to apply:** reuse for any future tenant-scoped model/signal tests. See [[audit-infrastructure]].
