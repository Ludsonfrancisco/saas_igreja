# Agent Memory Index

- [User profile](user_profile.md) — project owner, governance-strict workflow
- [Tenant provisioning quirks](project_tenant_provisioning.md) — auto_create_schema migrates SHARED_APPS too; public bootstrap pattern
- [Dev tooling (perf baseline)](project_dev_tooling.md) — nplusone + debug-toolbar wired dev-only; prod stays clean via base.py exclusion
- [libmagic PNG fixtures](project_libmagic_png_fixtures.md) — PNG test bytes need a real IHDR chunk or libmagic returns octet-stream
- [File context scoping](project_file_context_scoping.md) — FileAsset has no FK; ScopedFileQuerysetMixin derives scope from leadership M2Ms; no `coordinator` role (== leader)
- [Dashboard metrics scoping](project_dashboard_metrics_scoping.md) — church_metrics: community scopes attendance via Gathering.community; ministry via Person.ministries (no Gathering->Ministry FK)
