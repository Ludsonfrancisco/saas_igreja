---
name: files-download-audit
description: Sprint 6 Bloco 3 — secure file download (streaming, OD-021), files signals wiring, custom file_downloaded Signal, role gate per ACCESS_MATRIX
metadata:
  type: project
---

Sprint 6 Bloco 3 (download seguro + auditoria de arquivos) implemented.

**Why:** OD-021 chose streaming-through-the-view over R2 signed URLs — same route in dev (FS) and prod (R2), zero permanent public URL, reliable audit on every request.

**How to apply (patterns to reuse):**
- Download = streaming via `FileResponse` in `apps/files/responses.py::stream_file_asset` — opens `file_asset.file.open('rb')`, NEVER calls `.url()`. `as_attachment=True`, `content_type=mime_type`. The "no public URL" guarantee lives here and is asserted by `test_no_permanent_public_url` (checks `resp.streaming is True`, no `Location`, storage url bytes not in body).
- `FileDownloadView` (apps/files/views.py): `TenantRequiredMixin` + `FileDownloadRoleMixin` (roles `pastor,secretary,leader,treasurer` per ACCESS_MATRIX §3.8 "Download de arquivo"; Platform Admin ❌, member has no login OD-004) + `SingleObjectMixin` + `View`. FileAsset is a TENANT model, so `get_object()` is naturally tenant-scoped → cross-tenant/missing = Http404 (never 403, no existence leak).
- Audit wiring (P-ARQ-06): two signals in `apps/files/signals.py`, connected in `FilesConfig.ready()` with `dispatch_uid`:
  1. `post_save` of FileAsset created=True → `log_security_event('sensitive_file_upload', user_id=instance.uploaded_by_id, ...)`. (AuditLog create is automatic via AuditLogMixin global receiver — don't duplicate.)
  2. Custom `file_downloaded = Signal()` sent BY the view (read is not an ORM event) → receiver does `record_audit(action='read', instance=file_asset, user_id=...)` + `log_security_event('sensitive_file_download', ...)`.
- Route: `arquivos/<int:pk>/download/` namespace `files`, included once in `core/urls.py` (root urlconf, tenant-scoped via TenantMiddleware).
- SecurityLog payloads carry only ids/mime/size — no PII (TENANT-07). Asserted in tests.

**Gotcha:** stale `test_saas_igreja` DB from an interrupted run causes 124 SystemExit:2 collection errors ("database already exists"). Fix: `uv run pytest --create-db`. Full files+core run is slow (~7min).

Left for Bloco 4+: list view with context filters, authenticated delete view, templates, dashboard, matrix test updates. SPRINTS.md checkboxes NOT marked (owner does that). Links: [[audit_infrastructure]].
