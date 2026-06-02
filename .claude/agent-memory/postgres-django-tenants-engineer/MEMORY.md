# Agent Memory — postgres-django-tenants-engineer

- [Tenant schema isolation verification](tenant-isolation-verification.md) — how to prove core models land in tenant schemas, not public
- [Ruff DJ enforced](ruff-dj-str-required.md) — DJ ruleset is on; concrete models need __str__ even when spec gives them verbatim
- [Test DB schema names](test-fixture-schema-names.md) — church_a/church_b fixtures use schema_name tenant_a/tenant_b (not athos/bethel)
