"""Template tags da navegação do app.

`side_link` (Sprint 6.6 / Athos v2) renderiza um item VERTICAL da sidebar
(`.side-item`) — usado tanto na sidebar desktop quanto no drawer mobile.
Deriva o estado ATIVO de `request.path`.
"""

from django import template

register = template.Library()


def _is_active(request, path, exact=False, match=None):
    """Estado ativo de um item a partir de `request.path`.

    `match` (opcional) = prefixo usado SÓ para o ativo, quando o `href` difere da
    rota real (ex.: "Painel" aponta para `/` mas destaca em `/painel*`). Sem
    `match`: `exact` compara igualdade; senão, prefixo do `path`.
    """
    current = getattr(request, 'path', '') or ''
    if match:
        return current.startswith(match)
    if exact:
        return current == path
    return path != '/' and current.startswith(path)


@register.inclusion_tag('components/_side_link.html', takes_context=True)
def side_link(context, path, label, icon, exact=False, match=None):
    """Item VERTICAL da sidebar/drawer (Athos v2), com destaque do item atual."""
    active = _is_active(context.get('request'), path, exact=exact, match=match)
    return {'path': path, 'label': label, 'icon': icon, 'active': active}
