"""Sprint 2 / Frente 5 — Platform Admin & SupportAccess (RN-015 / RISK-009).

Bateria P0 do SPRINTS.md. Cobre os dois eixos do controle de acesso de Platform
Admin a um tenant:

- o MIDDLEWARE primario `PlatformAdminSupportMiddleware`, que bloqueia QUALQUER
  request de um Platform Admin a um tenant sem SupportAccess vigente (HTTP 403
  com body fixo), e libera+audita quando ha acesso ativo;
- o SERVICE layer (`grant_support_access` / `revoke_support_access`), que cria a
  janela de 4h e audita a concessao/revogacao no SecurityLog DA IGREJA-ALVO
  (schema do tenant), via `schema_context` — sem PII/justification no payload.

Particularidades de banco (django-tenants):
- requests de tenant usam `Client(HTTP_HOST='a.testserver')` (o Domain da fixture
  `church_a`); a request deixa o search_path no schema do tenant, restaurado para
  o public no teardown (`connection.set_schema_to_public()`).
- `@pytest.mark.django_db(transaction=True)` porque criar Church dispara DDL
  (auto_create_schema) que o rollback transacional padrao nao desfaz.
- o SecurityLog vive SO no schema de tenant; para asseri-lo consultamos dentro de
  `with schema_context(church.schema_name)`.

PII: nenhum dado real — emails sinteticos `@a.com`, justification de ticket.
"""

import pytest
from allauth.mfa.models import Authenticator
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.accounts.models import PlatformAdmin, SupportAccess, User
from apps.accounts.services import grant_support_access, revoke_support_access
from apps.core.models import SecurityLog

TENANT_URL = '/configuracoes/usuarios/'
TENANT_HOST = 'a.testserver'
BLOCK_BODY = b'Acesso negado: sem SupportAccess ativo.'
GOOD_PASSWORD = 'Senha@123'


@pytest.fixture
def tenant_client():
    """Client no host do tenant_a; restaura o public no teardown."""
    client = Client(HTTP_HOST=TENANT_HOST)
    yield client
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _enable_mfa(user):
    """Da MFA TOTP ao user (satisfaz o gate §215). O gate so checa EXISTENCIA de
    um Authenticator TOTP, entao um registro minimo basta (Authenticator vive no
    schema public, junto com User — TENANT-04)."""
    Authenticator.objects.create(
        user=user, type=Authenticator.Type.TOTP, data={'secret': 'x'}
    )


def _make_platform_admin(email='admin@plataforma.com', is_active=True, with_mfa=True):
    """Cria um User (publico, sem church) + seu PlatformAdmin.

    `with_mfa=True` por padrao: um PlatformAdmin real precisa de MFA (gate §215),
    entao a maioria dos testes o quer com MFA ativo. Os testes do proprio gate
    passam `with_mfa=False` para exercitar o bloqueio.
    """
    user = User.objects.create_user(email=email, password=GOOD_PASSWORD)
    admin = PlatformAdmin.objects.create(user=user, is_active=is_active)
    if with_mfa:
        _enable_mfa(user)
    return user, admin


def _security_logs(church, **filters):
    """SecurityLog gravado no schema da igreja-alvo (lista materializada)."""
    with schema_context(church.schema_name):
        return list(SecurityLog.objects.filter(**filters))


# --- 1. Middleware: bloqueio sem SupportAccess -----------------------------


@pytest.mark.django_db(transaction=True)
def test_platform_admin_blocked_without_support_access(tenant_client, church_a):
    """Platform Admin ativo SEM SupportAccess: 403 do MIDDLEWARE + log denied.

    O body fixo `Acesso negado: sem SupportAccess ativo.` confirma que o bloqueio
    veio do `PlatformAdminSupportMiddleware` (primario), e nao de um mixin de
    papel — o admin nem chega a tocar a view. Audita `platform_admin_access`
    com `denied=True` no SecurityLog do tenant (RISK-009).
    """
    user, _admin = _make_platform_admin()
    tenant_client.force_login(user)

    resp = tenant_client.get(TENANT_URL)

    assert resp.status_code == 403
    assert resp.content == BLOCK_BODY

    logs = _security_logs(
        church_a, event_type='platform_admin_access', payload__denied=True
    )
    assert len(logs) == 1
    assert logs[0].payload['reason'] == 'no_active_support_access'
    assert logs[0].payload['path'] == TENANT_URL
    assert logs[0].user_id == user.id


# --- 2. Service: grant cria janela de 4h + SecurityLog na igreja-alvo -------


@pytest.mark.django_db(transaction=True)
def test_grant_support_access_creates_4h_window_and_security_log(church_a):
    """grant_support_access: janela ~now+4h, ativo, e log na igreja-alvo sem PII."""
    _user, admin = _make_platform_admin()
    before = timezone.now()

    support_access = grant_support_access(
        admin=admin, church=church_a, justification='Ticket #123'
    )

    # Janela de 4h (tolerancia de alguns minutos para o tempo do teste).
    delta = support_access.expires_at - before
    assert (
        timezone.timedelta(hours=3, minutes=58)
        <= delta
        <= timezone.timedelta(hours=4, minutes=2)
    )
    assert support_access.ended_at is None
    assert support_access.is_active is True

    # SecurityLog gravado NO schema da igreja-alvo, com o id correto e SEM a
    # justification (PII de ticket nunca entra no payload — TENANT-07).
    logs = _security_logs(church_a, event_type='support_access_granted')
    assert len(logs) == 1
    payload = logs[0].payload
    assert payload['support_access_id'] == support_access.id
    assert payload['admin_id'] == admin.id
    assert 'expires_at' in payload
    assert 'Ticket #123' not in str(payload)
    assert 'justification' not in payload
    assert logs[0].user_id == admin.user_id


@pytest.mark.django_db(transaction=True)
def test_grant_support_access_rejects_empty_justification(church_a):
    """Justificativa vazia (ou so espacos) -> ValidationError, sem criar acesso."""
    _user, admin = _make_platform_admin()

    with pytest.raises(ValidationError):
        grant_support_access(admin=admin, church=church_a, justification='   ')

    assert SupportAccess.objects.count() == 0


# --- 2b. Gate §215: admin sem MFA nao concede acesso (RISK-009) -------------


@pytest.mark.django_db(transaction=True)
def test_grant_support_access_blocked_when_admin_has_no_mfa(church_a):
    """Gate §215: PlatformAdmin SEM MFA TOTP -> ValidationError, nada criado."""
    _user, admin = _make_platform_admin(with_mfa=False)

    with pytest.raises(ValidationError):
        grant_support_access(admin=admin, church=church_a, justification='Ticket')

    assert SupportAccess.objects.count() == 0
    # E o gate bloqueia ANTES de qualquer log de concessao.
    assert _security_logs(church_a, event_type='support_access_granted') == []


@pytest.mark.django_db(transaction=True)
def test_grant_support_access_allowed_when_admin_has_mfa(church_a):
    """Gate §215: PlatformAdmin COM MFA TOTP concede normalmente."""
    _user, admin = _make_platform_admin(with_mfa=True)

    support_access = grant_support_access(
        admin=admin, church=church_a, justification='Ticket'
    )

    assert support_access.is_active is True
    assert SupportAccess.objects.count() == 1


# --- 3. Middleware: acesso expirado nao conta como vigente ------------------


@pytest.mark.django_db(transaction=True)
def test_support_access_expired_auto_blocks(tenant_client, church_a):
    """SupportAccess com expires_at no PASSADO nao vale: middleware bloqueia (403)."""
    user, admin = _make_platform_admin()
    SupportAccess.objects.create(
        admin=admin,
        church=church_a,
        justification='Ticket antigo',
        expires_at=timezone.now() - timezone.timedelta(minutes=1),
    )
    tenant_client.force_login(user)

    resp = tenant_client.get(TENANT_URL)

    assert resp.status_code == 403
    assert resp.content == BLOCK_BODY


# --- 4. Middleware + service: revogacao bloqueia de imediato ----------------


@pytest.mark.django_db(transaction=True)
def test_revoke_support_access_blocks_immediately(tenant_client, church_a):
    """Concede -> passa pelo middleware; revoga -> a request seguinte e 403.

    Antes da revogacao, o admin com acesso vigente NAO recebe o body de bloqueio
    e o middleware audita `platform_admin_access` com `denied=False`. Apos
    `revoke_support_access`, a request imediata e bloqueada (403 + body fixo),
    com `ended_at` setado e `support_access_revoked` no SecurityLog da igreja-alvo.
    """
    user, admin = _make_platform_admin()
    support_access = grant_support_access(
        admin=admin, church=church_a, justification='Ticket #777'
    )
    tenant_client.force_login(user)

    # 1a request: acesso vigente -> NAO bloqueado.
    resp_allowed = tenant_client.get(TENANT_URL)
    assert resp_allowed.content != BLOCK_BODY
    allow_logs = _security_logs(
        church_a, event_type='platform_admin_access', payload__denied=False
    )
    assert len(allow_logs) == 1
    assert allow_logs[0].payload['support_access_id'] == support_access.id

    # Revoga.
    connection.set_schema_to_public()
    revoke_support_access(support_access=support_access)
    support_access.refresh_from_db()
    assert support_access.ended_at is not None

    revoke_logs = _security_logs(church_a, event_type='support_access_revoked')
    assert len(revoke_logs) == 1
    assert revoke_logs[0].payload['support_access_id'] == support_access.id
    assert revoke_logs[0].user_id == admin.user_id

    # 2a request: acesso encerrado -> bloqueado de imediato.
    resp_blocked = tenant_client.get(TENANT_URL)
    assert resp_blocked.status_code == 403
    assert resp_blocked.content == BLOCK_BODY


# --- Robustez ---------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_revoke_is_idempotent(church_a):
    """Revogar duas vezes nao cria 2o SecurityLog nem altera o `ended_at`."""
    _user, admin = _make_platform_admin()
    support_access = grant_support_access(
        admin=admin, church=church_a, justification='Ticket #1'
    )

    revoke_support_access(support_access=support_access)
    support_access.refresh_from_db()
    first_ended_at = support_access.ended_at

    revoke_support_access(support_access=support_access)
    support_access.refresh_from_db()

    assert support_access.ended_at == first_ended_at
    revoke_logs = _security_logs(church_a, event_type='support_access_revoked')
    assert len(revoke_logs) == 1


@pytest.mark.django_db(transaction=True)
def test_support_access_log_written_in_target_church_schema_only(church_a, church_b):
    """Isolamento (RISK-001): o log de grant para A existe em A e NUNCA em B."""
    _user, admin = _make_platform_admin()

    grant_support_access(admin=admin, church=church_a, justification='Ticket A')

    logs_a = _security_logs(church_a, event_type='support_access_granted')
    logs_b = _security_logs(church_b, event_type='support_access_granted')
    assert len(logs_a) == 1
    assert len(logs_b) == 0


@pytest.mark.django_db(transaction=True)
def test_normal_church_user_not_affected_by_middleware(tenant_client, church_a):
    """Usuario comum da igreja (sem PlatformAdmin) acessa normalmente (200).

    Prova que o `PlatformAdminSupportMiddleware` so penaliza Platform Admins: um
    Pastor comum passa direto, sem 403 e sem log de `platform_admin_access`.
    """
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)

    resp = tenant_client.get(TENANT_URL)

    assert resp.status_code == 200
    logs = _security_logs(church_a, event_type='platform_admin_access')
    assert logs == []


@pytest.mark.django_db(transaction=True)
def test_inactive_platform_admin_not_enforced_by_middleware(tenant_client, church_a):
    """PlatformAdmin INATIVO nao e tratado como admin: middleware nao bloqueia.

    O middleware filtra `is_active=True`; um admin desativado cai no caminho de
    usuario comum. Sem church o User nao e Pastor, entao a view aplica suas
    proprias barreiras (403 do PastorRequiredMixin), mas NUNCA o 403 do middleware
    (body fixo) — confirmamos pela AUSENCIA do body de bloqueio e de log de admin.
    """
    user, _admin = _make_platform_admin(is_active=False)
    tenant_client.force_login(user)

    resp = tenant_client.get(TENANT_URL)

    assert resp.content != BLOCK_BODY
    logs = _security_logs(church_a, event_type='platform_admin_access')
    assert logs == []
