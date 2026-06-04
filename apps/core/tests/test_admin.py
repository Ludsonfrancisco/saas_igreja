"""Sprint 2 / Frente 7 — TenantAdminMixin (SEC-01 / TENANT-05).

O `TenantAdminMixin` desliga o Django admin em produção (DEBUG=False) e preserva
o comportamento padrão em dev (DEBUG=True). Como nenhum `ModelAdmin` real é
registrado na Sprint 2, exercitamos o contrato via um ModelAdmin dummy.

O test runner roda com `DEBUG=False` (prod-like), então o caminho "desligado" é o
default; o caminho "dev" é forçado com `override_settings(DEBUG=True)`.
"""

import pytest
from django.contrib import admin
from django.test import RequestFactory, override_settings

from apps.accounts.models import User
from apps.core.admin import TenantAdminMixin


class _DummyAdmin(TenantAdminMixin, admin.ModelAdmin):
    pass


def _admin_and_request(user):
    model_admin = _DummyAdmin(User, admin.site)
    request = RequestFactory().get('/admin/')
    request.user = user
    return model_admin, request


@override_settings(DEBUG=False)
@pytest.mark.django_db
def test_admin_fully_disabled_in_production():
    """Prod (DEBUG=False): todas as permissões do admin negadas (até superuser)."""
    superuser = User.objects.create_superuser(email='root@x.com', password='Senha@123')
    model_admin, request = _admin_and_request(superuser)

    assert model_admin.has_module_permission(request) is False
    assert model_admin.has_view_permission(request) is False
    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_admin_enabled_in_dev_for_superuser():
    """Em dev (DEBUG=True) o mixin delega ao ModelAdmin padrão: superuser libera."""
    superuser = User.objects.create_superuser(email='root@x.com', password='Senha@123')
    model_admin, request = _admin_and_request(superuser)

    assert model_admin.has_module_permission(request) is True
    assert model_admin.has_view_permission(request) is True
    assert model_admin.has_add_permission(request) is True
    assert model_admin.has_change_permission(request) is True
    assert model_admin.has_delete_permission(request) is True


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_admin_in_dev_still_respects_underlying_permissions():
    """Mesmo em dev, um usuário comum (sem perms de admin) continua negado.

    Prova que o mixin não 'abre' o admin: em dev ele apenas delega ao
    `ModelAdmin`, que nega quem não tem permissão.
    """
    common = User.objects.create_user(email='membro@x.com', password='Senha@123')
    model_admin, request = _admin_and_request(common)

    assert model_admin.has_module_permission(request) is False
    assert model_admin.has_view_permission(request) is False
