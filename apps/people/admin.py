"""Admin de Pessoas — herda `TenantAdminMixin` (desligado em produção, SEC-01).

O admin é ferramenta de inspeção local (dev); em prod o `TenantAdminMixin` nega
todas as permissões. As views reais de Pessoa (CRUD + LGPD) vivem em
`apps/people/views.py` (Frente 2), protegidas por TenantRequiredMixin.
"""

from django.contrib import admin

from apps.core.admin import TenantAdminMixin
from apps.people.models import Person


@admin.register(Person)
class PersonAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'status', 'community')
    list_filter = ('status',)
    search_fields = ('name',)
