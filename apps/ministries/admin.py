"""Admin de Ministérios — herda `TenantAdminMixin` (desligado em produção, SEC-01)."""

from django.contrib import admin

from apps.core.admin import TenantAdminMixin
from apps.ministries.models import Ministry


@admin.register(Ministry)
class MinistryAdmin(TenantAdminMixin, admin.ModelAdmin):
    # `coordinators` é M2M (OD-019) — fora do list_display; vai no filter_horizontal.
    list_display = ('name', 'volunteers_needed', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    filter_horizontal = ('coordinators',)
