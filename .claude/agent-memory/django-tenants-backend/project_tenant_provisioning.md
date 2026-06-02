---
name: project-tenant-provisioning
description: Observed django-tenants behavior during tenant provisioning — auto_create_schema runs SHARED_APPS migrations into each tenant schema; public tenant bootstrap is required for the middleware
metadata:
  type: project
---

When a `Church` (TenantMixin, `auto_create_schema=True`) is saved, django-tenants 3.10.1 runs `migrate_schemas` against the NEW schema and applies ALL apps (SHARED_APPS like accounts/admin/auth/contenttypes/sessions AND TENANT_APPS) into that tenant schema, not only TENANT_APPS. Observed in Sprint 1 smoke-provisioning (tenant_athos, tenant_bethel).

**Why:** This is the django-tenants default migration behavior, not a misconfiguration. It matters for the Sprint 2 AuditLog/SecurityLog placement decision (TECH_SPEC §5.9.1): those models must live in the tenant schema, and `apps.core` is already in TENANT_APPS, so they will migrate there automatically.

**How to apply:** Do not be alarmed by SHARED_APPS tables appearing in tenant schemas during `create_church`. When working on §5.9.1, verify AuditLog/SecurityLog land in tenant schemas (they will, via apps.core in TENANT_APPS). The TenantMiddleware (TenantMainMiddleware subclass) requires a `public` tenant + `localhost` Domain to exist — `apps/tenants/services.py::ensure_public_tenant()` bootstraps this idempotently and is called by `create_church`.
