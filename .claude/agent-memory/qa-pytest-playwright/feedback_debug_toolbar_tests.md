---
name: debug-toolbar-tests
description: django-debug-toolbar in core.settings.dev breaks any test that exercises the test client; neutralize it in conftest, not settings
metadata:
  type: feedback
---

**RESOLVED as of Sprint 2 (verified 2026-06-02).** `core/settings/dev.py` now sets
`DEBUG_TOOLBAR_CONFIG = {'SHOW_TOOLBAR_CALLBACK': lambda request: django_settings.DEBUG}`,
reading `django_settings.DEBUG` at request time. Django forces `settings.DEBUG=False` during
tests, so the toolbar is inert. View tests using the test client (`test_user_list_view.py`,
`test_invite_views.py`) pass clean with NO `_disable_debug_toolbar` fixture — there is none in
conftest anymore, and none is needed.

**Why this note remains:** the original closure bug (lambda closing over module-level `DEBUG=True`)
was real on an earlier revision and caused `NoReverseMatch('djdt')` on any test-client response. If
someone reverts the callback to a captured constant, the crash returns. The signature to watch for is
`NoReverseMatch('djdt')` on otherwise-correct view tests.

**How to apply:** do NOT add a debug-toolbar-neutralizing fixture preemptively — current settings
handle it. Only revisit if test-client view tests start failing with `djdt` reverse errors. See
[[django-tenants-test-db]].
