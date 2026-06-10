"""Sprint 6.7 / Bloco 1 — service do Financeiro: criação, saldo, LGPD.

Cobertura (OD-024a):
- `create_transaction`: cria com `created_by`; recusa valor <= 0;
- `balance`: saldo = Σ entradas − Σ saídas (agregação no banco), com janela;
- `totals_by_category`: group-by por categoria;
- LGPD: purge da Pessoa-contribuinte preserva o lançamento (`contributor` SET_NULL).

Models de TENANT_APPS -> `schema_context` para ORM puro. DDL de criar Church exige
`@pytest.mark.django_db(transaction=True)`.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.utils import schema_context

from apps.finance import services
from apps.finance.models import Category, Transaction
from apps.people.models import Person


@pytest.fixture(autouse=True)
def _reset_schema():
    yield
    connection.set_schema_to_public()


class _Actor:
    """Stub mínimo de ator (só precisa de `.id` p/ `created_by`)."""

    id = 42


@pytest.mark.django_db(transaction=True)
def test_transaction_create_and_balance(church_a):
    """Saldo = entradas − saídas; `created_by` gravado; valor inválido recusado."""
    with schema_context(church_a.schema_name):
        dizimo = Category.objects.create(name='Dízimo', kind=Category.Kind.INCOME)
        oferta = Category.objects.create(name='Oferta', kind=Category.Kind.INCOME)
        energia = Category.objects.create(name='Energia', kind=Category.Kind.EXPENSE)

        services.create_transaction(
            user=_Actor(),
            category=dizimo,
            date=date(2026, 6, 1),
            amount=Decimal('500.00'),
        )
        services.create_transaction(
            user=_Actor(),
            category=oferta,
            date=date(2026, 6, 2),
            amount=Decimal('150.50'),
        )
        t = services.create_transaction(
            user=_Actor(),
            category=energia,
            date=date(2026, 6, 3),
            amount=Decimal('200.00'),
        )

        result = services.balance()

    assert t.created_by == 42
    assert result['income'] == Decimal('650.50')
    assert result['expense'] == Decimal('200.00')
    assert result['balance'] == Decimal('450.50')


@pytest.mark.django_db(transaction=True)
def test_transaction_create_rejects_non_positive(church_a):
    """Valor <= 0 levanta ValidationError (não cria lançamento)."""
    with schema_context(church_a.schema_name):
        cat = Category.objects.create(name='Dízimo', kind=Category.Kind.INCOME)
        with pytest.raises(ValidationError):
            services.create_transaction(
                user=_Actor(), category=cat, date=date(2026, 6, 1), amount=Decimal('0')
            )
        assert Transaction.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_balance_respects_period(church_a):
    """`start`/`end` recortam o saldo ao período."""
    with schema_context(church_a.schema_name):
        cat = Category.objects.create(name='Dízimo', kind=Category.Kind.INCOME)
        services.create_transaction(
            user=_Actor(), category=cat, date=date(2026, 5, 31), amount=Decimal('100')
        )
        services.create_transaction(
            user=_Actor(), category=cat, date=date(2026, 6, 10), amount=Decimal('300')
        )
        jun = services.balance(start=date(2026, 6, 1), end=date(2026, 6, 30))
    assert jun['income'] == Decimal('300')  # maio não conta


@pytest.mark.django_db(transaction=True)
def test_totals_by_category(church_a):
    """Group-by por categoria, ordenado do maior total p/ o menor."""
    with schema_context(church_a.schema_name):
        dizimo = Category.objects.create(name='Dízimo', kind=Category.Kind.INCOME)
        oferta = Category.objects.create(name='Oferta', kind=Category.Kind.INCOME)
        for _ in range(3):
            services.create_transaction(
                user=_Actor(),
                category=dizimo,
                date=date(2026, 6, 1),
                amount=Decimal('100'),
            )
        services.create_transaction(
            user=_Actor(), category=oferta, date=date(2026, 6, 1), amount=Decimal('50')
        )
        rows = services.totals_by_category(kind=Category.Kind.INCOME)
    assert [(r['name'], r['total']) for r in rows] == [
        ('Dízimo', Decimal('300')),
        ('Oferta', Decimal('50')),
    ]


@pytest.mark.django_db(transaction=True)
def test_contribution_person_set_null(church_a):
    """LGPD (RN-007): purge da Pessoa preserva o lançamento (`contributor`→NULL)."""
    with schema_context(church_a.schema_name):
        cat = Category.objects.create(name='Dízimo', kind=Category.Kind.INCOME)
        person = Person.objects.create(name='Irmão João')
        tx = services.create_transaction(
            user=_Actor(),
            category=cat,
            date=date(2026, 6, 1),
            amount=Decimal('250.00'),
            contributor=person,
        )
        assert tx.contributor_id == person.id

        # Purge físico da Pessoa (após anonimização + retenção, RN-006).
        person.delete()
        tx.refresh_from_db()

    assert tx.contributor_id is None  # SET_NULL
    assert tx.amount == Decimal('250.00')  # o lançamento histórico permanece
