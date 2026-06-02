---
name: ruff-dj-str-required
description: Ruff DJ ruleset is enabled project-wide; concrete Django models must define __str__ (DJ008)
metadata:
  type: feedback
---

Ruff `select` includes `DJ` (flake8-django) in pyproject.toml. Concrete models without
`__str__` trip DJ008 and fail the "ruff-clean" gate.

**Why:** project lint config enforces it; existing models (e.g. tenants) already define __str__.

**How to apply:** When a TECH_SPEC §5 model is given "verbatim" without a `__str__`, still add a
minimal `__str__` — it is not a field/Meta change and generates no migration (`makemigrations
--check --dry-run` stays "No changes detected"). The verbatim requirement covers fields/Meta/indexes;
`__str__` is additive and required to keep ruff clean. Migrations dir is excluded from ruff
(extend-exclude), so DJ008 only matters in models.py.
