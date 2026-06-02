---
name: user-owner
description: Project owner profile and collaboration constraints for SaaS Igreja QA work
metadata:
  type: user
---

Owner drives a multi-tenant Django 5.2 + django-tenants church SaaS, run sprint-by-sprint with strict governance (G-01..G-05 in CLAUDE.md / PRD §1.1).

Collaboration constraints to honor:
- Never run git (commit/push/merge/PR) — G-03. Leave changes in workspace for review.
- Stay strictly within the authorized task scope; ask before deciding anything touching an OPEN_DECISION or out-of-scope code/settings.
- Every test must cite a requirement (RF/RNF/RN/CA-XXX). Sprint 1 minimum tests cite RNF-022, RN-001, TENANT-01/05, P-ARQ-02/03.
- Code in English, single quotes in Python, Black line-length 88, Ruff clean. Interface text is pt-BR.
- Postgres real always; mock only external integrations (Redis/PG in /ready/ tests are monkeypatched, never stopped).
