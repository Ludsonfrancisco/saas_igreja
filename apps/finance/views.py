"""Views do Financeiro — CRUD + dashboard tenant-scoped (Sprint 6.7 / Bloco 2).

Acesso (ACCESS_MATRIX financeiro): **Pastor + Tesoureiro** (`TreasurerOrPastorMixin`)
sempre com `TenantRequiredMixin` (TENANT-05/AP-09). Defesa em 3 camadas (P-ARQ-08):
view (papel+tenant), service (regra de criação) e queryset (isolamento por schema).

Página "Gestão Financeira" (design `financeiro.html`, adaptada a dados reais):
KPIs de saldo/entradas/saídas/dizimistas + totais por categoria + movimentações
recentes; seções sem modelo (metas, contas/fundos) ficam "Em breve".
"""

import calendar as _calendar
import csv
from datetime import date

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.audit import record_audit
from apps.core.mixins import TenantRequiredMixin, TreasurerOrPastorMixin
from apps.finance import services
from apps.finance.forms import CategoryForm, TransactionForm
from apps.finance.models import Category, Transaction

MONTH_NAMES_PT = (
    '',
    'Janeiro',
    'Fevereiro',
    'Março',
    'Abril',
    'Maio',
    'Junho',
    'Julho',
    'Agosto',
    'Setembro',
    'Outubro',
    'Novembro',
    'Dezembro',
)


def _period(request):
    """(year, month, start, end, label) do mês pedido (`?year=&month=`) ou o atual."""
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if not 1 <= month <= 12:
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month
    start = date(year, month, 1)
    end = date(year, month, _calendar.monthrange(year, month)[1])
    return year, month, start, end, f'{MONTH_NAMES_PT[month]} {year}'


class FinanceBaseMixin(TenantRequiredMixin, TreasurerOrPastorMixin):
    """Gate comum do financeiro: tenant + (Pastor ou Tesoureiro)."""


class FinanceDashboardView(FinanceBaseMixin, TemplateView):
    """Página "Gestão Financeira": KPIs + totais por categoria + recentes."""

    template_name = 'finance/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year, month, start, end, label = _period(self.request)
        context['period_label'] = label
        context['period_year'] = year
        context['period_month'] = month
        context['month_balance'] = services.balance(start=start, end=end)
        context['total_balance'] = services.balance()
        context['contributors'] = services.active_contributors_count(
            start=start, end=end
        )
        context['by_category'] = services.totals_by_category(start=start, end=end)
        context['recent'] = services.recent_transactions()
        # Seletor de meses (6 últimos), mais recente primeiro.
        months = []
        y, m = year, month
        for _ in range(6):
            months.append({'year': y, 'month': m, 'label': f'{MONTH_NAMES_PT[m]} {y}'})
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        context['months'] = months
        return context


class TransactionListView(FinanceBaseMixin, ListView):
    """Extrato: lançamentos filtráveis por tipo/categoria/período."""

    model = Transaction
    template_name = 'finance/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 30

    def get_queryset(self):
        qs = Transaction.objects.select_related('category').order_by(
            '-date', '-created_at'
        )
        if kind := self.request.GET.get('kind'):
            qs = qs.filter(category__kind=kind)
        if cat := self.request.GET.get('category'):
            qs = qs.filter(category_id=cat)
        if start := self.request.GET.get('start'):
            qs = qs.filter(date__gte=start)
        if end := self.request.GET.get('end'):
            qs = qs.filter(date__lte=end)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_active=True)
        context['kind_choices'] = Category.Kind.choices
        context['filters'] = self.request.GET
        return context


class TransactionCreateView(FinanceBaseMixin, CreateView):
    """Cria lançamento via service. `?tipo=entrada|saida` trava o tipo da categoria."""

    model = Transaction
    form_class = TransactionForm
    template_name = 'finance/transaction_form.html'
    success_url = reverse_lazy('finance:dashboard')

    def _kind(self):
        tipo = self.request.GET.get('tipo')
        if tipo == 'saida':
            return Category.Kind.EXPENSE
        if tipo == 'entrada':
            return Category.Kind.INCOME
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['kind'] = self._kind()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kind = self._kind()
        context['title'] = (
            'Nova entrada'
            if kind == Category.Kind.INCOME
            else 'Nova despesa' if kind == Category.Kind.EXPENSE else 'Novo lançamento'
        )
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        services.create_transaction(
            user=self.request.user,
            category=data['category'],
            date=data['date'],
            amount=data['amount'],
            description=data.get('description', ''),
            payment_method=data['payment_method'],
            contributor=data.get('contributor'),
        )
        messages.success(self.request, 'Lançamento registrado.')
        # NÃO chamamos super().form_valid (faria form.save() — 2º lançamento,
        # pulando o service e o created_by). Redireciona direto.
        return redirect(self.success_url)


class TransactionUpdateView(FinanceBaseMixin, UpdateView):
    """Edita lançamento (AuditLog automático via AuditLogMixin)."""

    model = Transaction
    form_class = TransactionForm
    template_name = 'finance/transaction_form.html'
    success_url = reverse_lazy('finance:list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar lançamento'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Lançamento atualizado.')
        return super().form_valid(form)


class TransactionDeleteView(FinanceBaseMixin, DeleteView):
    """Exclui lançamento (AuditLog automático)."""

    model = Transaction
    template_name = 'finance/transaction_confirm_delete.html'
    success_url = reverse_lazy('finance:list')

    def form_valid(self, form):
        messages.success(self.request, 'Lançamento excluído.')
        return super().form_valid(form)


class CategoryListView(FinanceBaseMixin, ListView):
    """Categorias de entrada/saída."""

    model = Category
    template_name = 'finance/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.all()


class CategoryCreateView(FinanceBaseMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'finance/category_form.html'
    success_url = reverse_lazy('finance:category_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nova categoria'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Categoria criada.')
        return super().form_valid(form)


class CategoryUpdateView(FinanceBaseMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'finance/category_form.html'
    success_url = reverse_lazy('finance:category_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar categoria'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Categoria atualizada.')
        return super().form_valid(form)


class TransactionExportCSVView(FinanceBaseMixin, View):
    """Exporta os lançamentos (filtrados como o extrato) em CSV. Audita o export."""

    def get(self, request):
        qs = Transaction.objects.select_related('category').order_by('date')
        if kind := request.GET.get('kind'):
            qs = qs.filter(category__kind=kind)
        if start := request.GET.get('start'):
            qs = qs.filter(date__gte=start)
        if end := request.GET.get('end'):
            qs = qs.filter(date__lte=end)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="lancamentos.csv"'
        writer = csv.writer(response)
        writer.writerow(['Data', 'Tipo', 'Categoria', 'Valor', 'Forma', 'Descrição'])
        for t in qs:
            writer.writerow(
                [
                    t.date.isoformat(),
                    t.category.get_kind_display(),
                    t.category.name,
                    f'{t.amount:.2f}',
                    t.get_payment_method_display(),
                    t.description,
                ]
            )
        record_audit(
            action='export',
            model_name='Transaction',
            object_repr=f'CSV de lançamentos ({qs.count()} linhas)',
        )
        return response
