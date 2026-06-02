---
name: audit-infrastructure
description: How the AuditLog/SecurityLog auto-audit infra is wired in apps/core (Sprint 2, Front 1 wave 2)
metadata:
  type: project
---

Audit infrastructure built in Sprint 2 (Front 1, wave 2). Reusable plumbing that later fronts call.

- `apps/core/audit.py` — `record_audit(...)` (AuditLog) and `log_security_event(...)` (SecurityLog). Both: tenant_id from `connection.schema_name`; user_id/ip default to thread-local; PUBLIC-SCHEMA GUARD returns None silently (logs live only in tenant schemas); never raise (try/except + PII-free warning). Callers must pass sanitized payload (no passwords/tokens) to `log_security_event`.
- `apps/core/middleware.py` — `AuditContextMiddleware` (thread-local user_id+ip, cleared in finally even on exception) + module helpers `get_current_user_id()` / `get_current_ip()` (None outside a request). Uses REMOTE_ADDR only (XFF not trusted until Sprint 7 proxy config). MFARequiredForRoleMiddleware will live here in Sprint 7 — placeholder comment only, NOT implemented.
- Middleware registered in `core/settings/base.py` AFTER AuthenticationMiddleware, after TenantMiddleware (kept first).
- `apps/core/models.py` — `AuditLogMixin` abstract model (no fields, no table/migration). Marker only; signals detect via `isinstance`. AuditLog/SecurityLog do NOT inherit it (avoids recursion).
- `apps/core/signals.py` — global post_save/post_delete receivers; filter `isinstance(instance, AuditLogMixin)`; create/update via `created` flag; delete. Connected in `apps/core/apps.py` `ready()` (P-ARQ-06).
- `apps/core/sentry.py` — `before_send(event, hint)` recursively regex-masks email + BR phone in any string in the event; defensive never-raise. Sentry `sentry_sdk.init` in base.py is GUARDED by `SENTRY_DSN` (decouple, default '') — dev does NOT init. send_default_pii=False. tenant_id tagging deferred to Sprint 7.

**Why:** auditing must never break business ops; logs must never leak PII (TENANT-07); cross-schema FK forbidden (RN-014/TENANT-04).
**How to apply:** Later fronts (Auth=2, SupportAccess=5, MFA=6) call `log_security_event(...)` for their events — do NOT add that wiring in the audit-infra front. Make tenant models auto-audited by inheriting `AuditLogMixin`.
