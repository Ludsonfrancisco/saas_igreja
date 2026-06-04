"""Admin de Ministérios — herda `TenantAdminMixin` (desligado em produção, SEC-01)."""

from django.contrib import admin

from apps.core.admin import TenantAdminMixin
from apps.ministries.models import Ministry


@admin.register(Ministry)
class MinistryAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'coordinator', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
