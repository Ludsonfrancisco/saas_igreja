---
name: supportaccess-flow
description: Sprint 2 Frente 5 — Platform Admin & SupportAccess enforcement, where each SecurityLog is written and the schema_context gotcha
metadata:
  type: project
---

Frente 5 (RN-015 / RISK-009) wired Platform Admin SupportAccess enforcement.

**Where each SecurityLog `platform_admin_access`/`support_access_*` is written:**
- `support_access_granted` / `support_access_revoked` happen on the PLATFORM area
  (public schema). `log_security_event` has a public-schema guard that returns
  None silently — so grant/revoke MUST wrap the call in
  `with schema_context(church.schema_name): log_security_event(...)` to write into
  the TARGET church's tenant SecurityLog. This is the subtle bug-trap of the front.
  Lives in `apps/accounts/services.py` (`grant_support_access`/`revoke_support_access`).
- `platform_admin_access` (per-request access/deny to a tenant) happens IN tenant
  context, so `log_security_event` writes naturally — no schema_context needed.

**Primary enforcement = middleware, not mixin.** `PlatformAdminSupportMiddleware`
(apps/core/middleware.py) is the PRIMARY RISK-009 control: catches ANY tenant
request by a Platform Admin (1 indexed PlatformAdmin query only when authed in
tenant; normal church users return fast). Blocks with 403 before the view runs.
Placed AFTER AuditContextMiddleware in core/settings/base.py MIDDLEWARE.
`PlatformAdminWithSupportAccessMixin` (apps/core/mixins.py) is defense-in-depth —
its deny branch almost never fires because middleware blocks first.

**Two distinct mixins** in apps/core/mixins.py:
- `PlatformAdminRequiredMixin`: for PLATFORM-area views (public schema). Mirror-
  inverse of TenantRequiredMixin — requires active PlatformAdmin AND
  `schema_name == public` (Http404 if inside a tenant).
- `PlatformAdminWithSupportAccessMixin`: for tenant views accessed by a Platform
  Admin. Lazy imports inside dispatch to avoid apps.core <-> apps.accounts cycle.

**justification never goes in the log payload** (TENANT-07) — may contain ticket
PII; stays only on the SupportAccess model. `_SUPPORT_ACCESS_TTL = timedelta(hours=4)`.

**MFA gate deferred (Owner decision Opção A).** grant_support_access has ONLY a
`# TODO(Frente 6): exigir MFA do admin antes de conceder (RISK-009/§215)` hook —
allauth.mfa not installed yet, no mfa_enabled field, gate NOT implemented now.

Migration: `apps/core/migrations/0002_alter_securitylog_event_type.py` (AlterField
no-op adding support_access_granted/revoked choices).
