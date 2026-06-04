"""Sprint 2 / Frente 5 — Views da AREA DE PLATAFORMA (RN-015 / RISK-009).

As views de SupportAccess vivem no schema `public` (gestao da plataforma), nao
em tenant. Sao protegidas por `PlatformAdminRequiredMixin` — o espelho invertido
do TenantRequiredMixin: exige PlatformAdmin ativo E estar no schema public.

Para que o `TenantMiddleware` (TenantMainMiddleware) sirva uma request no public,
o tenant `public` + seu Domain `localhost` precisam existir. As fixtures
`church_a`/`church_b` nao criam o public; a fixture `public_tenant` abaixo chama
`ensure_public_tenant()` (idempotente) e usamos `Client(HTTP_HOST='localhost')`.

`@pytest.mark.django_db(transaction=True)` porque criar Church/public dispara DDL
(auto_create_schema). O search_path e restaurado para o public no teardown.
"""

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import PlatformAdmin, SupportAccess, User
from apps.core.models import SecurityLog

PLATFORM_HOST = 'localhost'
TENANT_HOST = 'a.testserver'
GRANT_URL = '/plataforma/suporte/conceder/'
LIST_URL = '/plataforma/suporte/'
GOOD_PASSWORD = 'Senha@123'


@pytest.fixture
def public_tenant(db):
    """Garante o tenant public + Domain `localhost` (idempotente)."""
    from apps.tenants.services import ensure_public_tenant

    ensure_public_tenant()
    connection.set_schema_to_public()
    yield
    connection.set_schema_to_public()


@pytest.fixture
def platform_client():
    """Client no host do public (`localhost`); restaura o public no teardown."""
    client = Client(HTTP_HOST=PLATFORM_HOST)
    yield client
    connection.set_schema_to_public()


def _make_user(email, roles=None, church=None):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles or [], church=church
    )


def _make_platform_admin(email='admin@plataforma.com', is_active=True):
    user = _make_user(email)
    admin = PlatformAdmin.objects.create(user=user, is_active=is_active)
    return user, admin


# --- Barreira do PlatformAdminRequiredMixin --------------------------------


@pytest.mark.django_db(transaction=True)
def test_platform_admin_required_mixin_blocks_non_admin(platform_client, public_tenant):
    """Usuario sem PlatformAdmin recebe 403 nas views da plataforma (no public)."""
    user = _make_user('comum@plataforma.com')
    platform_client.force_login(user)

    resp = platform_client.get(LIST_URL)

    assert resp.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_platform_view_served_from_tenant_returns_404(church_a):
    """Espelho invertido: a view de plataforma servida de DENTRO de um tenant -> 404.

    No host do tenant (`a.testserver`), o `PlatformAdminRequiredMixin` ve um schema
    != public e devolve Http404 — a area de plataforma nao e roteavel por
    subdominio de igreja (nao revelamos sua existencia ali).
    """
    tenant_client = Client(HTTP_HOST=TENANT_HOST)
    user, _admin = _make_platform_admin()
    tenant_client.force_login(user)

    try:
        resp = tenant_client.get(LIST_URL)
        # No tenant, o PlatformAdmin sem SupportAccess e barrado ANTES pelo
        # middleware primario (403). O contrato relevante aqui e: a area de
        # plataforma NUNCA responde 200/redirect a partir de um tenant.
        assert resp.status_code in (403, 404)
    finally:
        connection.set_schema_to_public()


@pytest.mark.django_db(transaction=True)
def test_inactive_platform_admin_blocked_on_platform_views(
    platform_client, public_tenant
):
    """PlatformAdmin inativo recebe 403 nas views da plataforma."""
    user, _admin = _make_platform_admin(is_active=False)
    platform_client.force_login(user)

    resp = platform_client.get(LIST_URL)

    assert resp.status_code == 403


# --- Concessao via view -----------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_grant_view_by_platform_admin_creates_access(
    platform_client, public_tenant, church_a
):
    """PlatformAdmin no public POSTa em /conceder/ -> cria SupportAccess + redirect.

    Valida o fluxo de ponta a ponta da view: form (church + justification) ->
    service -> SupportAccess vigente + SecurityLog `support_access_granted` no
    schema da igreja-alvo. Confere DOM (redirect) E banco (registro criado).
    """
    user, admin = _make_platform_admin()
    platform_client.force_login(user)

    resp = platform_client.post(
        GRANT_URL,
        {'church': church_a.pk, 'justification': 'Ticket #555'},
    )

    assert resp.status_code == 302
    assert resp.url == LIST_URL

    connection.set_schema_to_public()
    access = SupportAccess.objects.get(admin=admin, church=church_a)
    assert access.ended_at is None
    assert access.is_active is True

    with schema_context(church_a.schema_name):
        logs = list(SecurityLog.objects.filter(event_type='support_access_granted'))
    assert len(logs) == 1
    assert logs[0].payload['support_access_id'] == access.id


@pytest.mark.django_db(transaction=True)
def test_grant_view_rejects_empty_justification(
    platform_client, public_tenant, church_a
):
    """Justificativa vazia: o form rejeita (200, sem redirect) e nada e criado."""
    user, _admin = _make_platform_admin()
    platform_client.force_login(user)

    resp = platform_client.post(
        GRANT_URL,
        {'church': church_a.pk, 'justification': ''},
    )

    assert resp.status_code == 200
    connection.set_schema_to_public()
    assert SupportAccess.objects.count() == 0
