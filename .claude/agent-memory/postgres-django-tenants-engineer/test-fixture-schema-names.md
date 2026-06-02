---
name: test-fixture-schema-names
description: Test-DB tenant fixtures use schema_name tenant_a/tenant_b; dev DB has tenant_athos/tenant_bethel
metadata:
  type: project
---

Two distinct sets of tenant schema names — do not confuse them:
- **Dev DB** (docker `saas_igreja_db`): existing tenants are `tenant_athos`, `tenant_bethel`.
- **Test DB** (conftest.py fixtures church_a/church_b): create `tenant_a`, `tenant_b`
  via auto_create_schema, DROP SCHEMA on teardown.

**How to apply:** Isolation tests using `schema_context(...)` must pass `'tenant_a'`/`'tenant_b'`
(matching the fixtures), not the dev names. conftest also overrides `django_db_setup` to run
`migrate_schemas --shared` so public tables exist in the test DB. See [[tenant-isolation-verification]].
