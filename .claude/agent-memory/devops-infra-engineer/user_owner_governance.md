---
name: user-owner-governance
description: How the project owner wants infra/scaffold work delivered — review-first, owner-only versioning
metadata:
  type: user
---

The project owner (Ludson Correa) runs this project under strict SDD governance (G-01..G-05 in CLAUDE.md / PRD §1.1).

- Owner authorizes each sprint and each task explicitly before work starts (G-01, G-02).
- Owner is the ONLY one who runs git commit/push/merge or opens PRs (G-03). Leave all changes untracked in the workspace for review (G-04).
- Tasks are scoped tightly; do not exceed the stated sub-task list even when adjacent work is obvious (e.g. settings/apps belong to a different agent wave).

**How to apply:** When given a scaffold/infra task, produce files only, validate locally (uv lock / uv sync / ruff / black), then report. Never stage or commit. Flag cost-affecting or open-decision (OD-xxx) scope creep back to the owner instead of deciding.
