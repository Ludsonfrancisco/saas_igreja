"""Template tags do Financeiro — formatação monetária pt-BR (Sprint 6.7)."""

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def brl(value):
    """Formata um valor como Real brasileiro: `R$ 1.450,50` (negativos com `-`)."""
    try:
        v = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    sign = '-' if v < 0 else ''
    # `,.2f` -> "1,450.50" (en); troca para pt-BR "1.450,50".
    s = f'{abs(v):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return f'{sign}R$ {s}'
