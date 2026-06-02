---
name: debug-toolbar-tests
description: django-debug-toolbar in core.settings.dev breaks any test that exercises the test client; neutralize it in conftest, not settings
metadata:
  type: feedback
---

Tests run under `core.settings.dev` (matches CI), which installs django-debug-toolbar with `DEBUG_TOOLBAR_CONFIG['SHOW_TOOLBAR_CALLBACK'] = lambda request: DEBUG`. That lambda closes over the module-level `DEBUG=True`, ignoring Django's test-time `settings.DEBUG=False`. So the toolbar tries to render on any test-client response and crashes with `NoReverseMatch('djdt')` because `__debug__/` URLs only exist under real DEBUG.

**Why:** the dev settings comment claims the toolbar "fica inerte automaticamente" in tests — it does not, due to the closure bug.

**How to apply:**
- Root conftest has an `autouse` fixture `_disable_debug_toolbar(settings)` that sets `settings.DEBUG_TOOLBAR_CONFIG = {'SHOW_TOOLBAR_CALLBACK': lambda request: False}`. Keep it; any test using `client` (health, future view/permission/isolation tests) depends on it.
- The real fix is in `core/settings/dev.py` (callback should read `settings.DEBUG` or check a test flag), but that's a settings change — out of scope unless the owner authorizes. Flag it if touching settings.
- This will matter a lot from Sprint 2+ when permission/isolation tests hammer the test client. See [[django-tenants-test-db]].
