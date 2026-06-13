"""URLs de configuração da Igreja (namespace 'tenants'), tenant-scoped sob
`configuracoes/`."""

from django.urls import path

from apps.tenants.views import ChurchSettingsView

app_name = 'tenants'

urlpatterns = [
    path('configuracoes/igreja/', ChurchSettingsView.as_view(), name='settings'),
]
