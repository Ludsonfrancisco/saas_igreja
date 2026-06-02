---
name: auth-allauth-axes
description: How allauth 65 + axes 8 are wired for email login, lockout, password reset, and SecurityLog events (Sprint 2 Front 2)
metadata:
  type: project
---

Authentication built in Sprint 2 (Front 2). allauth 65.18 + axes 8.3 (installed in `.venv`, NOT the system python — always use `.venv/bin/python`).

PLACEMENT (TENANT-04): `django.contrib.sites`, `allauth`, `allauth.account`, `axes` all live in SHARED_APPS (public schema) because their models reference the PUBLIC User. They ship their own migrations -> `migrate_schemas --shared` applies account_*/axes_*/django_site to public; `makemigrations` for our apps yields "No changes detected". SITE_ID=1 required by allauth.

MIDDLEWARE order (TenantMiddleware stays first): ... AuthenticationMiddleware -> allauth.account.middleware.AccountMiddleware -> AuditContextMiddleware -> Messages -> XFrame -> axes.middleware.AxesMiddleware (last).

AUTHENTICATION_BACKENDS order: AxesStandaloneBackend (FIRST) -> EmailBackend -> allauth AuthenticationBackend -> ModelBackend.

allauth 65 settings (modern names; the old ACCOUNT_AUTHENTICATION_METHOD/EMAIL_REQUIRED/USERNAME_REQUIRED are DEPRECATED): `ACCOUNT_LOGIN_METHODS={'email'}`, `ACCOUNT_SIGNUP_FIELDS=['email*','password1*','password2*']`, `ACCOUNT_USER_MODEL_USERNAME_FIELD=None`, `ACCOUNT_EMAIL_VERIFICATION='none'`, `ACCOUNT_ADAPTER='apps.accounts.adapter.AccountAdapter'`.

Signup is CLOSED via `AccountAdapter.is_open_for_signup()->False` (invite-only, Frente 4). The login form field is `login` (not `email`/`username`).

SecurityLog event wiring (handlers in `apps/accounts/signals.py`, connected in `AccountsConfig.ready()` with dispatch_uid; imports are LATE inside ready() because axes/allauth signal modules need the app registry):
- login_success <- django `user_logged_in`
- login_failure <- django `user_login_failed` (user_id=None, NO email in payload — anti-enumeration + TENANT-07)
- lockout <- axes `user_locked_out`
- password_reset_completed <- allauth `password_reset` (fires on actual reset, token consumed)
- password_reset_requested -> NOT a signal: done in `AccountAdapter.send_password_reset_mail` (allauth only calls it for EXISTING users -> we have user.id AND it preserves no-enumeration; allauth emits no "reset requested" signal).

axes config: AXES_FAILURE_LIMIT=5, AXES_COOLOFF_TIME=timedelta(minutes=15), AXES_LOCKOUT_PARAMETERS=[['username','ip_address']], AXES_RESET_ON_SUCCESS=True. axes 8 lockout HTTP status is **429** (not 403). `AXES_USERNAME_FORM_FIELD='login'` is NOT enough: the user_login_failed `credentials` dict uses key `email`/`username` (not `login`), so axes records username=None and lockout degrades to IP-only. FIX: `AXES_USERNAME_CALLABLE='apps.accounts.axes_helpers.get_username'` reads login/email/username from credentials OR request.POST, lowercased.

PASSWORD_RESET_TIMEOUT=86400 (24h). PasswordPolicyValidator in `apps/accounts/validators.py` (8+ chars, 1 digit, 1 special, not-equal/not-containing email-localpart/name) registered in AUTH_PASSWORD_VALIDATORS. Prod security headers/cookies already correct — `check --deploy` against prod settings is CLEAN (no warnings).

**Why:** email-only login (P-ARQ-03), brute-force lockout (SEC-02), no email enumeration (§15.1), audit every auth event without PII (TENANT-07).
**How to apply:** Frente 4 (invites) reuses the closed-signup adapter; Frente 6 (MFA) adds `allauth.mfa` to SHARED_APPS; Sprint 7 MFA enforcement lives in apps/core/middleware (placeholder there). See [[audit-infrastructure]] for log_security_event, [[tenant-testing-gotchas]] for the test patterns below.
