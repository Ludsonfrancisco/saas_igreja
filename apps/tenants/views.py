"""Views de configuração da Igreja (tenant atual).

`ChurchSettingsView` (RF-002 parcial / RF-126-127 · F2): o Pastor edita os rótulos
configuráveis (Comunidade/Ministério) + o título do líder. Edita o `request.tenant`
(model público `Church`); serve sob o domínio do tenant.
"""

from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from apps.core.mixins import PastorRequiredMixin, TenantRequiredMixin
from apps.tenants.forms import ChurchSettingsForm
from apps.tenants.models import Church


class ChurchSettingsView(TenantRequiredMixin, PastorRequiredMixin, UpdateView):
    """Configurações da igreja — só Pastor (ACCESS_MATRIX §3.9 / RF-002)."""

    model = Church
    form_class = ChurchSettingsForm
    template_name = 'tenants/church_settings.html'
    success_url = reverse_lazy('tenants:settings')

    def get_object(self, queryset=None):
        # O tenant atual (resolvido pelo TenantMiddleware) é a igreja a editar.
        return self.request.tenant

    def form_valid(self, form):
        messages.success(self.request, 'Configurações da igreja salvas.')
        return super().form_valid(form)
