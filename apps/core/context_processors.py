"""Context processors do core (Sprint 6.5 / Bloco 1).

`church_theme` expõe o tema visual da igreja atual para o `base.html` injetar como
CSS variables em `:root` — base neutra Athos + **acento por igreja** (DS-01).

O tenant atual é resolvido pelo `TenantMiddleware` (django-tenants) em
`request.tenant` (instância de `Church`, model público). Em páginas públicas (schema
public, sem tenant) ou se algo faltar, caímos nos defaults Athos — nunca quebra.
"""

# Defaults da Paleta Athos (espelham `Church.accent_color`/`hot_color` e o input.css).
_DEFAULT_ACCENT = '#7C3F06'
_DEFAULT_ACCENT_2 = '#5A2D04'
_DEFAULT_HOT = '#FF9C1A'


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
