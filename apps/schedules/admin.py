"""Admin de Escalas — herda `TenantAdminMixin` (desligado em produção, SEC-01)."""

from django.contrib import admin

from apps.core.admin import TenantAdminMixin
from apps.schedules.models import Schedule, ScheduleConflictApproval


@admin.register(Schedule)
class ScheduleAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('person', 'ministry', 'gathering', 'role')
    list_filter = ('ministry',)
    search_fields = ('role',)


@admin.register(ScheduleConflictApproval)
class ScheduleConflictApprovalAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('schedule', 'approved_by_id', 'approved_at')
