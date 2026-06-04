"""Admin de Comunidades — herda `TenantAdminMixin` (desligado em produção, SEC-01)."""

from django.contrib import admin

from apps.communities.models import Community
from apps.core.admin import TenantAdminMixin


@admin.register(Community)
class CommunityAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'leader', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
