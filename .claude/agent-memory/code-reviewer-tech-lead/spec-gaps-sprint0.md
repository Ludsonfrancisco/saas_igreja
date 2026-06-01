---
name: spec-gaps-sprint0
description: Inconsistencies and gaps found validating docs/TECH_SPEC.md against PRD in Sprint 0 (2026-06-01)
metadata:
  type: project
---

Tech Lead validation of `docs/TECH_SPEC.md` on 2026-06-01. Verdict: APPROVED WITH RESERVATIONS. Gaps to track (none block Sprint 1; several block Sprint 2/3 implementation if not fixed first).

**Why:** TECH_SPEC is the technical base for Sprint 1. These are doc-level inconsistencies, not code bugs (no code exists yet).

**How to apply:** When reviewing Sprint 1+ code touching these areas, check whether the underlying spec gap was resolved first; if the code silently picks one interpretation of an ambiguous spec, flag it and escalate (G-05).

Key gaps (full detail given to owner in report):
- TEST_STRATEGY conftest fixtures use `role='pastor'` (singular) but model is `roles ArrayField` (RN-003a). Fixtures contradict the model — will not run. Must be `roles=['pastor']`.
- `User.church` is `on_delete=CASCADE` (TECH_SPEC §5.2). Deleting a Church hard-deletes its public Users; AuditLog uses `user_id IntegerField` so audit trail keeps dangling ids. No spec statement on Church deletion policy (suspend vs delete). RF-003 only suspends. Clarify.
- AuditLog/SecurityLog declared "lives in tenant schema" but coded as plain `models.Model` in `apps/core/models.py`; core also holds BaseModel/mixins (SHARED). Need explicit TENANT_APPS vs SHARED_APPS placement so AuditLog migrates into tenant schemas only. Risk of landing in public.
- `Church(TenantMixin)` redefines `created_at` while BaseModel also defines it — but Church does NOT inherit BaseModel (it inherits TenantMixin). Consistent, but `Plan` model (public) does not inherit BaseModel either — violates P-ARQ-02 literally ("todo model"). Decide if public infra models are exempt.
- `consent_given_at` validation location unspecified: RNF-007 says "Person.save OR form". P-ARQ / service layer (create_person) is where plan check lives. Pick service-layer + form, document, so it is enforced on CSV import too (import bypasses forms).
- MFARequiredForRoleMiddleware (RF-018b, Sprint 7) named in PRD but not in TECH_SPEC middleware list (§2 only TenantMiddleware + optional headers). Add to spec.
- `python-magic` / `python-decouple` / `django-anymail[brevo]` / `django-storages` / `redis` / `nplusone` appear in PRD/SPRINTS but are NOT in TECH_SPEC §1 stack table. Stack table is incomplete vs decided deps.
- RNF-011 (<500ms/500 rows) and RNF-012/020 (Lighthouse, WCAG AA) have no architectural support described in TECH_SPEC (no caching/index strategy section, no frontend a11y section).
- Open decisions touching code not surfaced in TECH_SPEC §13: OD-004 (member login → accounts scope), OD-010 (log retention → AuditLog/SecurityLog growth), OD-014 (double confirm anonymize). §13 lists only closed ones.
- TECH_SPEC §13 omits OD-015 (GitHub Actions) and OD-016 (RTO/RPO) from "decisões fechadas" even though both are closed in OPEN_DECISIONS history and used elsewhere in the spec.
