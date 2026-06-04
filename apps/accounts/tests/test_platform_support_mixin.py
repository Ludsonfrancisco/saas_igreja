"""Sprint 2 / Frente 5 — PlatformAdminWithSupportAccessMixin (defense-in-depth).

O controle PRIMARIO de RISK-009 e o `PlatformAdminSupportMiddleware`, que bloqueia
ANTES de qualquer view rodar; por isso, em integracao, o ramo de "deny" deste
mixin quase nunca dispara (o middleware o sombreia). Aqui exercitamos o mixin
DIRETAMENTE (RequestFactory + view dummy) para provar que a SEGUNDA LINHA de
defesa funciona caso o middleware seja removido/reordenado:

- usuario sem PlatformAdmin -> PermissionDenied (403);
- PlatformAdmin inativo -> PermissionDenied;
- PlatformAdmin ativo SEM SupportAccess -> PermissionDenied + SecurityLog
  `platform_admin_access` (denied=True) no schema do tenant;
- PlatformAdmin ativo COM SupportAccess vigente -> libera a view.

`schema_context(church.schema_name)` deixa o search_path no schema do tenant
(`tenant, public`): os models publicos (User/PlatformAdmin/SupportAccess) seguem
acessiveis e o SecurityLog (tabela de tenant) e gravado/consultado no lugar certo.
`transaction=True` porque criar Church dispara DDL (auto_create_schema).
"""

import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone
from django.views import View
from django_tenants.utils import schema_context

from apps.accounts.models import PlatformAdmin, SupportAccess, User
from apps.core.mixins import PlatformAdminWithSupportAccessMixin
from apps.core.models import SecurityLog

GOOD_PASSWORD = 'Senha@123'


class _ProtectedView(PlatformAdminWithSupportAccessMixin, View):
    """View minima so para exercitar o dispatch do mixin."""

    def get(self, request, *args, **kwargs):
        return HttpResponse('ok')


def _request(user, tenant):
    request = RequestFactory().get('/qualquer/')
    request.user = user
    request.tenant = tenant
    return request


def _platform_admin(email='admin@plataforma.com', is_active=True):
    user = User.objects.create_user(email=email, password=GOOD_PASSWORD)
    admin = PlatformAdmin.objects.create(user=user, is_active=is_active)
    return user, admin


@pytest.mark.django_db(transaction=True)
def test_mixin_denies_user_without_platform_admin(church_a):
    """Usuario comum (sem PlatformAdmin) -> PermissionDenied."""
    user = User.objects.create_user(email='comum@x.com', password=GOOD_PASSWORD)
    with schema_context(church_a.schema_name):
        with pytest.raises(PermissionDenied):
            _ProtectedView.as_view()(_request(user, church_a))


@pytest.mark.django_db(transaction=True)
def test_mixin_denies_inactive_platform_admin(church_a):
    """PlatformAdmin inativo nao e tratado como admin -> PermissionDenied."""
    user, _admin = _platform_admin(is_active=False)
    with schema_context(church_a.schema_name):
        with pytest.raises(PermissionDenied):
            _ProtectedView.as_view()(_request(user, church_a))


@pytest.mark.django_db(transaction=True)
def test_mixin_denies_admin_without_support_access_and_logs(church_a):
    """Admin ativo SEM SupportAccess -> PermissionDenied + log denied no tenant."""
    user, _admin = _platform_admin()
    with schema_context(church_a.schema_name):
        with pytest.raises(PermissionDenied):
            _ProtectedView.as_view()(_request(user, church_a))
        logs = list(
            SecurityLog.objects.filter(
                event_type='platform_admin_access', payload__denied=True
            )
        )
    assert len(logs) == 1
    assert logs[0].payload['reason'] == 'no_active_support_access'
    assert logs[0].user_id == user.id


@pytest.mark.django_db(transaction=True)
def test_mixin_allows_admin_with_active_support_access(church_a):
    """Admin ativo COM SupportAccess vigente -> libera a view (200)."""
    user, admin = _platform_admin()
    SupportAccess.objects.create(
        admin=admin,
        church=church_a,
        justification='Ticket #9',
        expires_at=timezone.now() + timezone.timedelta(hours=4),
    )
    with schema_context(church_a.schema_name):
        resp = _ProtectedView.as_view()(_request(user, church_a))
    assert resp.status_code == 200
    assert resp.content == b'ok'
