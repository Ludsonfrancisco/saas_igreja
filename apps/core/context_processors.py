"""Context processors do core (Sprint 6.5 / Bloco 1).

`church_theme` expõe o tema visual da igreja atual para o `base.html` injetar como
CSS variables em `:root` — base neutra Athos + **acento por igreja** (DS-01).

O tenant atual é resolvido pelo `TenantMiddleware` (django-tenants) em
`request.tenant` (instância de `Church`, model público). Em páginas públicas (schema
public, sem tenant) ou se algo faltar, caímos nos defaults Athos — nunca quebra.
"""

# Defaults = MARCA OIKONOS v2 (terra + âmbar). Espelham o :root do input.css.
# Uma igreja sem cor customizada herda a identidade Oikonos v2 (Athos v2 · Sprint 6.6).
# Accent ajustado de #C2552C → #BC5028 p/ passar WCAG AA (texto branco-quente
# sobre o accent). Espelha o :root do input.css. Confirmar com o dono (G-05).
_DEFAULT_ACCENT = '#BC5028'
_DEFAULT_ACCENT_2 = '#A8431F'
_DEFAULT_HOT = '#EBB45C'


def church_theme(request):
    """Cores/logo da igreja atual para o tema do app (CSS vars no base.html).

    Retorna sempre as três cores (com fallback Athos) + o logo da igreja, se houver.
    `accent_2` (tom mais escuro do acento) ainda não é campo de `Church` — usa o
    default; quando virar configurável, basta ler aqui.
    """
    church = getattr(request, 'tenant', None)

    accent = getattr(church, 'accent_color', '') or _DEFAULT_ACCENT
    hot = getattr(church, 'hot_color', '') or _DEFAULT_HOT
    logo = getattr(church, 'logo', None)

    return {
        'church': church,
        'theme_accent': accent,
        'theme_accent_2': _DEFAULT_ACCENT_2,
        'theme_hot': hot,
        'theme_logo_url': logo.url if logo else '',
        'church_name': getattr(church, 'name', '') or 'Oikonos',
    }
