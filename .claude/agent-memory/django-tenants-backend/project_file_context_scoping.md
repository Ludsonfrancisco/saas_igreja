---
name: file-context-scoping
description: How FileAsset (no FK) is scoped per role via related_model/related_object_id; coordinator == leader role
metadata:
  type: project
---

`FileAsset` (apps/files) has NO context FK — the link to a Person/Community/Ministry
is the string pair `related_model` + `related_object_id` (TECH_SPEC §5.8). Sprint 6
Bloco 4 added `ScopedFileQuerysetMixin` in `apps/files/views.py`, reused by both the
list view and the download view (closes the Bloco 3 "(autorizado)" gap).

Scope rules (ACCESS_MATRIX §3.8):
- Pastor / Secretary short-circuit, see ALL tenant files.
- `leader` role covers BOTH "Líder de Comunidade" AND "Coordenador de Ministério" —
  there is NO `coordinator` role in `User.Role`. Same convention as
  `schedules.PastorOrCoordinatorMixin` (required_roles `('pastor','leader')`). So a
  leader sees the UNION of community files (ids from
  `Community.objects.filter(leaders__user_id=user.id)`) and ministry files (ids from
  `Ministry.objects.filter(coordinators__user_id=user.id)`).
- Treasurer: files with `related_model='finance'`.
- Empty predicate => `.none()` (NOT match-all) to avoid intra-tenant leak.

`related_object_id` is a CharField, so Community/Ministry pk ids are cast to str
before `__in`. Context filter params (`?related_model=&related_object_id=`) intersect
the already-scoped queryset, so a filter can never widen a role's scope (P-ARQ-08).

**Why:** the no-FK design means scope can't be a simple `select_related`/queryset
filter on a relation — it's a `Q`-OR over string fields derived from the leadership
M2Ms. Future dashboard (Bloco 5) and `test_*_matrix` (Bloco 6) must reuse this same
derivation, not invent a new source of truth.
**How to apply:** when adding any file-aware view, mix in `ScopedFileQuerysetMixin`
and call `get_scoped_file_queryset()`; never filter FileAsset by role inline.

Delete = Pastor-only (`PastorRequiredMixin`); Secretary does NOT delete (resolved
2026-06-05 in favor of ACCESS_MATRIX §3.8). No SecurityLog event_type exists for file
deletion in `SecurityLog.EVENT_CHOICES` — AuditLog 'delete' (via AuditLogMixin) covers
the trail; do NOT add a migration for a delete event unless the owner asks.
