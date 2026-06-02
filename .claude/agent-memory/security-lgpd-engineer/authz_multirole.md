---
name: authz-multirole
description: Frente 3 multi-role authorization — where role/scope mixins, services, and the last-pastor guard live and their conventions
metadata:
  type: project
---

Sprint 2 Frente 3 (autorizacao multi-role, RN-003a/RN-004/P-ARQ-08) implemented.

**Where things live:**
- Role/scope mixins appended to `apps/core/mixins.py` (alongside `TenantRequiredMixin`): `RoleRequiredMixin` (base, `required_roles: tuple`, raises `PermissionDenied`), `PastorRequiredMixin`, `LeaderOrPastorMixin`, `TreasurerOrPastorMixin`, `ScopedToCommunityMixin`, `ScopedToMinistryMixin`. Implemented VERBATIM from `docs/ACCESS_MATRIX.md §4.1`.
- `apps/accounts/services.py` (NEW): `change_roles`, `deactivate_user`, `reactivate_user`. Light service layer (P-ARQ-04).
- `apps/accounts/views.py` + `apps/accounts/urls.py` (NEW): `UserListView` at `/configuracoes/usuarios/` (included in `core/urls.py`). Template `apps/accounts/templates/accounts/user_list.html`.

**Conventions / gotchas:**
- Mixin MRO on views: `TenantRequiredMixin, <RoleMixin>, View` — tenant/login barrier first.
- `ScopedTo*` mixins are deliberately model-agnostic (pure lookup-string filters `leader__user__id` / `coordinator__user__id`); they do NOT import Community/Ministry (those are Sprint 3). Pastor short-circuits (returns unfiltered qs).
- Last-pastor guard (RN-004) helper `_has_other_active_pastor` filters `roles__contains=['pastor']` + `is_active=True`, excludes self. Multi-role aware (`'pastor' in roles`, never equality). Applied to `change_roles` AND extended conservatively to `deactivate_user`.
- Services log via `apps.core.audit` helpers: AuditLog(action='update') + SecurityLog. `actor` -> `user_id` (author); affected user -> `payload['target_user_id']`. Roles are NOT PII — safe in payload.
- SecurityLog event values used: `role_change`, `user_deactivated`, `user_reactivated` (literals from `apps/core/models.py` EVENT_CHOICES).

**Test gotchas confirmed:**
- Services must run inside `schema_context('tenant_a')` for audit helpers to persist (public-schema guard).
- `LOGIN_URL` default is `/accounts/login/` (Django default), NOT allauth's `/contas/login/` — anonymous redirect tests should assert `'login' in resp.url` + `next=` param, not the exact path. (Possible follow-up: set LOGIN_URL to the allauth path.)
- Inactive user login: allauth redirects 302 to `/contas/inactive/` and never sets `_auth_user_id` (good — assert both).

See [[auth_allauth_axes]] for Frente 2 auth wiring, [[audit_infrastructure]] for the helpers.
