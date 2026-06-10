"""Service layer do Financeiro (Sprint 6.7 / OD-024a).

Camada fina (P-ARQ-04): concentra a criação de lançamento (com `created_by`) e as
contas de **saldo/totais**, que saem 100% de agregação no banco do TENANT ATUAL
(`Sum`/`aggregate`; nunca laço Python sobre queryset — P-ARQ-09). Isolamento por
tenant é automático (`Category`/`Transaction` são TENANT_APPS — TENANT-04).
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q, Sum

from apps.finance.models import Category, Transaction

ZERO = Decimal('0.00')


def create_transaction(
    *,
    user,
    category,
    date,
    amount,
    description='',
    payment_method=Transaction.PaymentMethod.CASH,
    contributor=None,
):
    """Cria um lançamento. `amount` deve ser positivo (o sinal vem do `kind`).

    `user` é o ator (request.user) — vira `created_by` (TENANT-04). AuditLog é
    automático (AuditLogMixin). Levanta `ValidationError` se o valor não for > 0.
    """
    if amount is None or amount <= 0:
        raise ValidationError('O valor do lançamento deve ser maior que zero.')
    return Transaction.objects.create(
        category=category,
        date=date,
        amount=amount,
        description=description or '',
        payment_method=payment_method,
        contributor=contributor,
        created_by=getattr(user, 'id', None),
    )


def _scoped_qs(*, start=None, end=None, category_id=None):
    qs = Transaction.objects.all()
    if start is not None:
        qs = qs.filter(date__gte=start)
    if end is not None:
        qs = qs.filter(date__lte=end)
    if category_id is not None:
        qs = qs.filter(category_id=category_id)
    return qs


def balance(*, start=None, end=None):
    """Saldo do período: `{'income', 'expense', 'balance'}` (Decimal).

    `income` = Σ valor de categorias-entrada; `expense` = Σ saídas; `balance` =
    income − expense. UM `aggregate` com `filter` por `category__kind` (P-ARQ-09).
    """
    agg = _scoped_qs(start=start, end=end).aggregate(
        income=Sum('amount', filter=Q(category__kind=Category.Kind.INCOME)),
        expense=Sum('amount', filter=Q(category__kind=Category.Kind.EXPENSE)),
    )
    income = agg['income'] or ZERO
    expense = agg['expense'] or ZERO
    return {'income': income, 'expense': expense, 'balance': income - expense}


def totals_by_category(*, kind=None, start=None, end=None):
    """Totais por categoria no período (group-by no banco), maior → menor.

    Lista de dicts `{'category_id', 'name', 'kind', 'total'}`. `kind` opcional
    recorta a entradas OU saídas.
    """
    qs = _scoped_qs(start=start, end=end)
    if kind is not None:
        qs = qs.filter(category__kind=kind)
    rows = (
        qs.values('category_id', 'category__name', 'category__kind')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    return [
        {
            'category_id': r['category_id'],
            'name': r['category__name'],
            'kind': r['category__kind'],
            'total': r['total'] or ZERO,
        }
        for r in rows
    ]


def recent_transactions(*, limit=8):
    """Movimentações recentes (para o card do financeiro), mais novas primeiro.

    `select_related('category')` evita N+1 ao exibir nome/sinal (P-ARQ-09). NÃO
    eager-load `contributor`: o card não o exibe (nplusone reclamaria de load inútil).
    """
    return Transaction.objects.select_related('category').order_by(
        '-date', '-created_at'
    )[:limit]


def active_contributors_count(*, start=None, end=None):
    """Nº de contribuintes (Pessoas) DISTINTOS com entrada no período (dizimistas).

    Conta `Person` distintas em lançamentos de categoria-entrada com `contributor`
    preenchido — agregação no banco (P-ARQ-09).
    """
    return (
        _scoped_qs(start=start, end=end)
        .filter(contributor__isnull=False, category__kind=Category.Kind.INCOME)
        .values('contributor_id')
        .distinct()
        .count()
    )
