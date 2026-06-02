---
name: invite-email-test-pattern
description: How to assert email sending in tests (mail.outbox needs locmem override) and the schema rules for Invite/User service tests
metadata:
  type: project
---

Pattern for testing anything that sends email or exercises Invite/User services (Frente 4 convites, and any future flow using `django.core.mail.send_mail`).

**Email backend:** the suite runs under `core.settings.dev`, which sets
`EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'`. The console backend does NOT
populate `django.core.mail.outbox`. Any test asserting an email was sent MUST decorate with
`@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')` and call
`mail.outbox.clear()` before the action (other setup like `create_user` doesn't email, but be safe).
There is no test-settings file forcing locmem globally.

**Why:** `_send_invite_email` in `apps/accounts/services.py` uses `send_mail(fail_silently=False)`.
Without the locmem override, `mail.outbox` stays empty and the assert silently passes/fails wrong.

**Schema rules for Invite/User service tests:** `Invite` and `User` are SHARED_APPS models (live in
`public`), so the services work even called from the public schema — most service tests need no
`schema_context`. BUT `record_audit`/`log_security_event` have a public-schema guard and only persist
in a TENANT schema. If a test verifies the audit trail, wrap the service call in
`schema_context('tenant_a')` (mirror `test_authz_services.py`). Frente 4 invite tests intentionally do
NOT assert the audit trail (the service writes audit only when in a tenant), so they run in public and
skip `schema_context` — keeps them simple and fast.

**View tests for invites:** mirror `test_user_list_view.py` — `Client(HTTP_HOST='a.testserver')`,
`@pytest.mark.django_db(transaction=True)` (Church creation is DDL), teardown
`connection.set_schema_to_public()`. `InviteAcceptView` is PUBLIC (no login); cross-tenant token at
another host returns 404 (the view checks `invite.church_id != request.tenant.id`).

**Files:** `apps/accounts/tests/test_invites_services.py`, `test_invites_extra.py`,
`test_invite_views.py`. All 23 green; `apps/accounts` prod-code coverage 94.0% (gate 90%).
See [[django-tenants-test-db]].
