---
name: dev-tooling-perf-baseline
description: nplusone + django-debug-toolbar are dev-only; how they are wired and why prod stays clean
metadata:
  type: project
---

Sprint 1 "Performance baseline" wired two dev-only tools, configured EXCLUSIVELY in `core/settings/dev.py` (never base.py / prod.py).

- nplusone: `'nplusone.ext.django'` in INSTALLED_APPS, `NPlusOneMiddleware` after TenantMiddleware, `NPLUSONE_RAISE = True` (P-ARQ-09 / RNF-024 — any N+1 raises and breaks tests). No DB models, so no migration/tenant concern.
- django-debug-toolbar: `'debug_toolbar'` app, `DebugToolbarMiddleware` placed right AFTER TenantMiddleware, `INTERNAL_IPS=['127.0.0.1','localhost']`, and `DEBUG_TOOLBAR_CONFIG={'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG}` so it works under Docker/odd dev IPs but stays inert in tests (Django forces DEBUG=False in tests).
- URLs: `core/urls.py` registers `__debug__/` only inside `if settings.DEBUG:`, with the `import debug_toolbar` INSIDE the guard so prod never imports it.

**Why:** prod.py only does `from .base import *` + a security block, so keeping dev tools out of base.py is what guarantees prod cleanliness. Verified via `DJANGO_SETTINGS_MODULE=core.settings.prod` import asserting neither app/middleware is present.

**How to apply:** when adding future dev-only tooling, follow this same pattern — dev.py only, rebuild MIDDLEWARE explicitly keeping `apps.tenants.middleware.TenantMiddleware` FIRST. Confirmed versions: nplusone 1.0.0 (pulls blinker), django-debug-toolbar 6.3.0. See [[tenant-provisioning]].
