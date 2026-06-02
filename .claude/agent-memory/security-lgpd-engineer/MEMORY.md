# Security/LGPD Engineer — Memory Index

- [Audit Infrastructure](audit_infrastructure.md) — where record_audit/log_security_event/AuditLogMixin/signals/Sentry before_send live and how they're wired
- [Tenant Testing Gotchas](tenant_testing_gotchas.md) — django-tenants test conventions: transaction=True for DDL, schema_context, managed=False model stubs, auth-flow client host + schema reset, axes state purge
- [Auth: allauth + axes](auth_allauth_axes.md) — Sprint 2 Front 2 email login/lockout/reset wiring, SHARED_APPS placement, modern allauth 65 settings, SecurityLog event signals
