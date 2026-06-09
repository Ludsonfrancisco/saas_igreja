"""Sprint 6.5 / Bloco 6 — tema por igreja no base.html (DS-01).

`church_theme` injeta o acento da `Church` atual como CSS var em `:root`. Aqui
garantimos que a cor CUSTOMIZADA da igreja (não o fallback Athos) chega na resposta.
"""

import pytest
from django.db import connection
from django.test import Client


@pytest.mark.django_db(transaction=True)
def test_base_template_renders_church_theme(church_a):
    """A accent_color da Church aparece como `--accent` no HTML renderizado."""
    church_a.accent_color = '#123456'
    church_a.save(update_fields=['accent_color'])

    client = Client(HTTP_HOST='a.testserver')
    resp = client.get('/contas/login/')  # página pública que renderiza base.html
    connection.set_schema_to_public()

    assert resp.status_code == 200
    assert '--accent: #123456' in resp.content.decode()


def test_church_theme_falls_back_to_oikonos_without_tenant(rf):
    """Sem tenant (página pública/public schema) → defaults Oikonos, nunca quebra."""
    from apps.core.context_processors import church_theme

    request = rf.get('/')
    # rf não seta request.tenant → getattr cai no fallback.
    ctx = church_theme(request)

    # Default = acento da marca Oikonos v2 (Athos v2 · Sprint 6.6). #BC5028 = #C2552C
    # ajustado p/ contraste WCAG AA do botão primário.
    assert ctx['theme_accent'] == '#BC5028'
    assert ctx['church_name'] == 'Oikonos'
