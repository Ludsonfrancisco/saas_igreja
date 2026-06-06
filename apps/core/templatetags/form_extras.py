"""Helpers de formulário para os templates (Sprint 6.5 / Bloco 3).

`add_class` injeta classes CSS no widget de um BoundField, permitindo estilizar
inputs do Django com Tailwind sem mexer nos forms Python. `is_checkbox` ajuda o
parcial a tratar checkbox de forma diferente (label ao lado, não input full-width).
"""

from django import forms
from django import template

register = template.Library()


@register.filter
def add_class(field, css):
    """Renderiza o widget do `field` com as classes CSS dadas (mescla com as existentes)."""
    attrs = dict(field.field.widget.attrs)
    existing = attrs.get('class', '')
    attrs['class'] = f'{existing} {css}'.strip()
    return field.as_widget(attrs=attrs)


@register.filter
def is_checkbox(field):
    """True se o widget for um checkbox (para layout label-ao-lado)."""
    return isinstance(field.field.widget, forms.CheckboxInput)
