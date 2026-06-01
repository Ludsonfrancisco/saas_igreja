---
name: spec-doc-map
description: Where each governance, architecture, anti-pattern, and tenancy rule is defined across PRD.md and docs/
metadata:
  type: reference
---

Source-of-truth layout for SaaS Igreja spec (pre-implementation, SDD).

- `PRD.md` — product source of truth. §1.1 governance G-01..05; §11 RF-001..101; §12 RNF-001..024; §13 RN-001..015; §14 TENANT-01..07; §18 data model; §27 RISK-001..014; §29 decisions.
- `docs/TECH_SPEC.md` — technical source of truth. §1 stack + §1.1 proibições; §3 P-ARQ-01..09; §5 full models; §7 SEC-01..07; §9 AP-01..13; §10 notas A1..A5; §12 healthcheck + CI/CD.
- `docs/ACCESS_MATRIX.md` — role × module × action matrix; mixins (§4.1); multi-role union; SupportAccess.
- `docs/TEST_STRATEGY.md` — §3 coverage gates per app; §6 mandatory tests; §9 Definition of Done; §10 TAP-01..08.
- `docs/SPRINTS.md` — 8 sprints (0–7), tasks as checkboxes, per-sprint min tests + completion criteria.
- `docs/OPEN_DECISIONS.md` — closed (OD-002/003/003a/006/007/012/015/016) + open (OD-001/004/005/008/009/010/011/013/014).

Coverage gates: core/accounts/tenants/files = 90%; people/communities/ministries/gatherings/schedules = 80%; dashboard = 70%.

Conflict resolution: most specific + recent wins; PRD wins on scope, TECH_SPEC wins on technical decision; unresolved → OPEN_DECISIONS + most conservative on security/tenancy.
