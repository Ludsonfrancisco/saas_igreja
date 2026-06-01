---
name: project-scaffold-tooling
description: Sprint 1 scaffold tooling decisions — uv groups, Ruff/Black quote style, CI contract, WeasyPrint caveat
metadata:
  type: project
---

Sprint 1 scaffold established the packaging/tooling baseline (no Django code yet — that is a later wave).

- Django package will be `core`; settings split `core.settings.{base,dev,prod}`; apps live under `apps/`. pyproject tooling is coherent with this but does NOT create those files.
- uv with PEP 735 `[dependency-groups] dev` (ruff, black, pytest, pytest-django, pytest-cov, pip-audit, safety). `uv sync` installs dev group by default — matches CI `uv sync --frozen`.
- Black uses `skip-string-normalization = true` and Ruff `format.quote-style = "single"` because STYLE-01 mandates single quotes in Python.
- CI (`.github/workflows/ci.yml`) is authoritative for the contract: Python 3.12, `uv sync --frozen`, ruff/black/pip-audit/safety, `pytest --cov=apps --cov-fail-under=80`. DATABASE_URL `postgres://saas:saas@localhost:5432/saas_igreja`. docker-compose dev creds must stay coherent (saas/saas/saas_igreja, postgres:15, redis:7).
- docker-compose `web` service is behind profile `app` (off by default) so `docker compose up` brings only db+redis while Django code is absent. db/redis never depend on web.
- Dockerfile is multi-stage (builder venv via uv → slim production, non-root, CMD targets `core.wsgi:application` once it exists).

**Why:** WeasyPrint (>=62) is in runtime deps ONLY because the scaffold sub-task listed it explicitly; TECH_SPEC §10 A4 marks it Phase 2 (MVP uses browser print). It pulls ~200MB of system libs (pango/cairo/gdk-pixbuf). Do not actually use WeasyPrint in MVP code.

**How to apply:** When extending infra, keep dev/CI/compose Postgres creds in sync. nplusone + django-debug-toolbar belong to the "Performance baseline" block, a separate wave — do not add them under scaffold scope. See [[user-owner-governance]].
