"""Admin de Encontros — herda `TenantAdminMixin` (desligado em produção, SEC-01)."""

from django.contrib import admin

from apps.core.admin import TenantAdminMixin
from apps.gatherings.models import Gathering


@admin.register(Gathering)
class GatheringAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('date', 'gathering_type', 'title', 'community')
    list_filter = ('gathering_type',)
    search_fields = ('title',)
    date_hierarchy = 'date'
