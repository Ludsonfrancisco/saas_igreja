"""Template tags da navegação do app (Sprint 6.5 / Bloco 2).

`nav_link` renderia um item de menu com estado ATIVO derivado de `request.path`
(`exact=True` para a home `/`; senão, prefixo). Usado no sidebar e no drawer mobile.
"""

from django import template

register = template.Library()


@register.inclusion_tag('components/_nav_link.html', takes_context=True)
def nav_link(context, path, label, icon, exact=False, match=None):
    """Item de navegação (link + ícone Lucide) com destaque do item atual.

    `match` (opcional) = prefixo de caminho usado SÓ para o estado ativo, quando o
    `href` difere da rota real (ex.: "Painel" aponta para `/` mas destaca em
    `/painel*`). Sem `match`: `exact` compara igualdade; senão, prefixo do `path`.
    """
    request = context.get('request')
    current = getattr(request, 'path', '') or ''
    if match:
        active = current.startswith(match)
    elif exact:
        active = current == path
    else:
        active = path != '/' and current.startswith(path)
    return {'path': path, 'label': label, 'icon': icon, 'active': active}
