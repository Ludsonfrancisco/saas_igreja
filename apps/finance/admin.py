"""Admin do Financeiro — herda `TenantAdminMixin` (desligado em produção, SEC-01)."""

from django.contrib import admin

from apps.core.admin import TenantAdminMixin
from apps.finance.models import Category, Transaction


@admin.register(Category)
class CategoryAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'kind', 'is_active')
    list_filter = ('kind', 'is_active')
    search_fields = ('name',)


@admin.register(Transaction)
class TransactionAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('date', 'category', 'amount', 'payment_method')
    list_filter = ('category__kind', 'payment_method', 'date')
    search_fields = ('description',)
    autocomplete_fields = ('category',)
