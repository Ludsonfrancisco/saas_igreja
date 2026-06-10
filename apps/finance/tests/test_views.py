"""Sprint 6.7 / Bloco 2 — views do Financeiro: escopo, dashboard, CSV, CRUD.

Cobertura (ACCESS_MATRIX financeiro / OD-024a):
- `test_treasurer_scope`: Pastor+Tesoureiro acessam (200); Secretário/Líder/Membro 403;
- `test_finance_dashboard_totals`: KPIs (saldo/entradas/saídas) corretos no contexto;
- `test_finance_export_csv`: CSV com cabeçalho + linhas; gera AuditLog `export`;
- criação de lançamento pela view (service, `created_by`); render real da página.

Stub de template (locmem) nos testes de escopo/contexto; render real onde valida o HTML.
Host `a.testserver`; criar Church (DDL) => `transaction=True`.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.test import Client, override_settings
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.finance.models import Category, Transaction

GOOD_PASSWORD = 'Senha@123'
DASH_URL = '/financeiro/'
CSV_URL = '/financeiro/lancamentos/csv/'

stub_templates = override_settings(
    TEMPLATES=[
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': False,
            'OPTIONS': {
                'loaders': [
                    (
                        'django.template.loaders.locmem.Loader',
                        {
                            'finance/dashboard.html': 'ok',
                            'finance/transaction_list.html': 'ok',
                            'finance/transaction_form.html': 'ok',
                        },
                    ),
                ],
                'context_processors': [
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                ],
            },
        }
    ]
)


@pytest.fixture
def tenant_client():
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


def _user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


# --------------------------------------------------------------------------- #
# Escopo de papel (Pastor + Tesoureiro)
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    'roles,expected',
    [
        (['pastor'], 200),
        (['treasurer'], 200),
        (['secretary'], 403),
        (['leader'], 403),
        (['member'], 403),
    ],
)
def test_treasurer_scope(tenant_client, church_a, roles, expected):
    """Só Pastor e Tesoureiro entram no Financeiro; os demais 403."""
    user = _user(church_a, f'{roles[0]}@a.com', roles)
    tenant_client.force_login(user)
    assert tenant_client.get(DASH_URL).status_code == expected


# --------------------------------------------------------------------------- #
# Dashboard — totais corretos
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
def test_finance_dashboard_totals(tenant_client, church_a):
    """KPIs do mês: entradas, saídas e saldo agregados corretamente."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        dizimo = Category.objects.create(name='Dízimo', kind=Category.Kind.INCOME)
        energia = Category.objects.create(name='Energia', kind=Category.Kind.EXPENSE)
        Transaction.objects.create(
            category=dizimo, date=date(2026, 6, 5), amount=Decimal('800')
        )
        Transaction.objects.create(
            category=energia, date=date(2026, 6, 6), amount=Decimal('300')
        )

    tenant_client.force_login(pastor)
    resp = tenant_client.get(DASH_URL, {'year': 2026, 'month': 6})
    assert resp.status_code == 200
    assert resp.context['month_balance']['income'] == Decimal('800')
    assert resp.context['month_balance']['expense'] == Decimal('300')
    assert resp.context['month_balance']['balance'] == Decimal('500')


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_finance_export_csv(tenant_client, church_a):
    """CSV traz cabeçalho + uma linha por lançamento e gera AuditLog `export`."""
    from apps.core.models import AuditLog

    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        dizimo = Category.objects.create(name='Dízimo', kind=Category.Kind.INCOME)
        Transaction.objects.create(
            category=dizimo, date=date(2026, 6, 5), amount=Decimal('800')
        )
        Transaction.objects.create(
            category=dizimo, date=date(2026, 6, 6), amount=Decimal('120')
        )

    tenant_client.force_login(pastor)
    resp = tenant_client.get(CSV_URL)
    assert resp.status_code == 200
    assert resp['Content-Type'].startswith('text/csv')
    body = resp.content.decode('utf-8')
    assert 'Data,Tipo,Categoria,Valor' in body
    assert body.count('Dízimo') == 2
    with schema_context(church_a.schema_name):
        assert AuditLog.objects.filter(action='export').exists()


# --------------------------------------------------------------------------- #
# Criação de lançamento pela view (service aplicado)
# --------------------------------------------------------------------------- #
@stub_templates
@pytest.mark.django_db(transaction=True)
def test_transaction_create_via_view(tenant_client, church_a):
    """POST cria o lançamento com `created_by` do ator (Tesoureiro)."""
    treasurer = _user(church_a, 'tes@a.com', ['treasurer'])
    with schema_context(church_a.schema_name):
        cat = Category.objects.create(name='Oferta', kind=Category.Kind.INCOME)

    tenant_client.force_login(treasurer)
    resp = tenant_client.post(
        '/financeiro/lancamentos/novo/?tipo=entrada',
        {
            'category': cat.id,
            'date': '2026-06-10',
            'amount': '250.00',
            'description': 'Oferta especial',
            'payment_method': 'pix',
        },
    )
    assert resp.status_code == 302
    with schema_context(church_a.schema_name):
        tx = Transaction.objects.get()
        assert tx.amount == Decimal('250.00')
        assert tx.created_by == treasurer.id


# --------------------------------------------------------------------------- #
# Render real da página (pega erro de template/url/filtro brl)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_finance_dashboard_renders_real(tenant_client, church_a):
    """A página Financeiro renderiza o template real sem erro."""
    pastor = _user(church_a, 'pastor@a.com', ['pastor'])
    with schema_context(church_a.schema_name):
        dizimo = Category.objects.create(name='Dízimo', kind=Category.Kind.INCOME)
        Transaction.objects.create(
            category=dizimo, date=date(2026, 6, 5), amount=Decimal('1450.50')
        )

    tenant_client.force_login(pastor)
    resp = tenant_client.get(DASH_URL)
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'Gestão Financeira' in body
    assert 'Saldo geral' in body
    assert 'R$' in body  # filtro brl aplicado
