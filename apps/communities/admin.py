"""Admin de Comunidades — herda `TenantAdminMixin` (desligado em produção, SEC-01)."""

from django.contrib import admin

from apps.communities.models import Community
from apps.core.admin import TenantAdminMixin


@admin.register(Community)
class CommunityAdmin(TenantAdminMixin, admin.ModelAdmin):
    # `leaders` é M2M (OD-019) — não vai em list_display; fica no filter_horizontal.
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    filter_horizontal = ('leaders',)
