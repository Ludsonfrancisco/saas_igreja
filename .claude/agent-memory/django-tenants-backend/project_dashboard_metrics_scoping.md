---
name: dashboard-metrics-scoping
description: church_metrics scope semantics — community scopes attendance via Gathering.community; ministry has no Gathering FK so it scopes via Person.ministries
metadata:
  type: project
---

`apps/dashboard/services.py::church_metrics(*, community_ids=None, ministry_ids=None)`
returns a serializable dict of numbers for the role-scoped dashboards (Sprint 6 Bloco 5,
ACCESS_MATRIX §3.9).

Scope semantics (decision, documented in the module docstring):
- both None => full church view (Pastor).
- `community_ids`: People via `Person.community__in`; attendance via
  `Attendance.gathering__community__in` (the Gathering->Community FK EXISTS).
- `ministry_ids`: People via `Person.ministries__in` (M2M); attendance via
  `Attendance.person__ministries__in` — because **there is NO Gathering->Ministry FK**
  in the data model. So ministry attendance = presence of that ministry's people in ANY
  gathering. This was a deliberate choice (the alternative, per-ministry gatherings,
  has no schema support).
- empty set (`[]`) => zeroed metric, never full view (conservative, P-ARQ-08). Mirrors
  the [[file-context-scoping]] rule that an empty predicate must not match everything.

**Why:** the three dashboards (Pastor/Leader/Coordinator) need a single scoped metric
function; the asymmetry (community has a gathering FK, ministry doesn't) forces two
different attendance-scoping paths.

**How to apply:** if Bloco 6 matrices or future work touch dashboard metrics, reuse
`church_metrics` and respect that ministry attendance is person-derived, not gathering-derived.
Views short-circuit Pastor/Secretary to the full view even on the simplified dashboards
(§3.9 "Pastor ✅ everywhere"); Leader/Coordinator never short-circuit.

Attendance window is `ATTENDANCE_WINDOW_DAYS = 30`, filtered on `Gathering.date` (not
created_at), is_present=True only. `people_by_status` seeds all `Person.Status` at 0 then
overlays a single group-by (no Python loops over querysets, P-ARQ-09).
