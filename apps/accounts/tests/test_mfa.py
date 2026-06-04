"""Sprint 2 / Frente 6 — MFA opt-in (TOTP + recovery codes) — RF-018a / OD-002.

Bateria P0 do SPRINTS.md (§185-187, §222, §251-252). Cobre:

- setup do TOTP via a tela NATIVA do allauth.mfa e login passando a exigir o
  segundo fator depois de ativado (`test_mfa_totp_opt_in_setup_and_login`);
- recovery codes (os "8 backup codes" do §186) de uso unico
  (`test_mfa_backup_codes_single_use`);
- disparo de `SecurityLog` `mfa_enabled`/`mfa_disabled` — e SO no TOTP (recovery
  codes auto-gerados nao contam como novo fator);
- a pagina pt-BR "Seguranca da conta" refletindo o status.

Contexto multi-tenant: usuarios comuns vivem num tenant; o `SecurityLog` so existe
no schema do tenant, entao as requests usam `Client(HTTP_HOST='a.testserver')`
(Domain de `church_a`) e os logs sao consultados dentro do schema da igreja. O
`Authenticator` do MFA, porem, e SHARED (public, junto com User — TENANT-04).

`@pytest.mark.django_db(transaction=True)` porque criar Church dispara DDL
(auto_create_schema). Tolerancia TOTP elevada para 1 janela nos testes que
computam codigos, eliminando flake de virada de janela (default e 0).

PII: nenhum dado real — emails sinteticos, codigos derivados de segredos de teste.
"""

import time

import pytest
from allauth.mfa import app_settings as mfa_app_settings
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    generate_totp_secret,
    hotp_value,
)
from allauth.mfa.utils import is_mfa_enabled
from django.test import Client, override_settings
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.core.models import SecurityLog

TENANT_HOST = 'a.testserver'
GOOD_PASSWORD = 'Senha@123'
LOGIN_URL = '/contas/login/'
ACTIVATE_URL = '/contas/2fa/totp/activate/'
DEACTIVATE_URL = '/contas/2fa/totp/deactivate/'
AUTHENTICATE_URL = '/contas/2fa/authenticate/'
SECURITY_URL = '/contas/seguranca/'
SECRET_SESSION_KEY = 'mfa.totp.secret'


@pytest.fixture
def tenant_client():
    """Client no host do tenant_a; restaura o public no teardown."""
    from django.db import connection

    client = Client(HTTP_HOST=TENANT_HOST)
    yield client
    connection.set_schema_to_public()


def _make_member(church, email='membro@a.com'):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=['member'], church=church
    )


def _totp_code(secret):
    """Codigo TOTP valido para a janela atual (mesma matematica do allauth)."""
    counter = int(time.time()) // mfa_app_settings.TOTP_PERIOD
    return format_hotp_value(hotp_value(secret, counter))


def _logs(church, **filters):
    with schema_context(church.schema_name):
        return list(SecurityLog.objects.filter(**filters))


# --- 1. Setup do TOTP + login exigindo o segundo fator ----------------------


@override_settings(MFA_TOTP_TOLERANCE=1)
@pytest.mark.django_db(transaction=True)
def test_mfa_totp_opt_in_setup_and_login(tenant_client, church_a):
    """Usuario ativa TOTP pela tela nativa; depois o login exige o codigo (RF-018a).

    Fase SETUP: logado (sem MFA), o usuario abre a tela de ativacao (que semeia o
    segredo na sessao), confirma com um codigo valido -> `is_mfa_enabled` True e
    `SecurityLog('mfa_enabled')` gravado no schema do tenant (§222).

    Fase LOGIN: numa sessao NOVA, login so com senha NAO completa — redireciona
    para o desafio 2FA e a area logada continua barrada; so apos POSTar o codigo
    TOTP o acesso e liberado.
    """
    member = _make_member(church_a)

    # SETUP — login so com senha (ainda sem MFA: prova que e opt-in, nao forcado).
    resp = tenant_client.post(
        LOGIN_URL, {'login': member.email, 'password': GOOD_PASSWORD}
    )
    assert resp.status_code == 302
    assert tenant_client.get(SECURITY_URL).status_code == 200  # logado

    # Abre a ativacao: o allauth semeia o segredo TOTP na sessao.
    tenant_client.get(ACTIVATE_URL)
    secret = tenant_client.session[SECRET_SESSION_KEY]
    resp = tenant_client.post(ACTIVATE_URL, {'code': _totp_code(secret)})
    assert resp.status_code == 302

    member.refresh_from_db()
    assert is_mfa_enabled(member, [Authenticator.Type.TOTP]) is True
    logs = _logs(church_a, event_type='mfa_enabled')
    assert len(logs) == 1
    assert logs[0].user_id == member.id
    assert logs[0].payload == {'method': 'totp'}

    # LOGIN — sessao nova: senha sozinha nao basta (redireciona ao desafio 2FA).
    fresh = Client(HTTP_HOST=TENANT_HOST)
    resp = fresh.post(LOGIN_URL, {'login': member.email, 'password': GOOD_PASSWORD})
    assert resp.status_code == 302
    assert AUTHENTICATE_URL in resp.url
    # Ainda NAO autenticado: area logada redireciona de volta para login.
    assert fresh.get(SECURITY_URL).status_code == 302

    # Completa com o codigo TOTP -> autenticado.
    resp = fresh.post(AUTHENTICATE_URL, {'code': _totp_code(secret)})
    assert resp.status_code == 302
    assert fresh.get(SECURITY_URL).status_code == 200


# --- 2. Recovery codes: 8 codigos de uso unico (§186) -----------------------


@pytest.mark.django_db(transaction=True)
def test_mfa_backup_codes_single_use(church_a):
    """Recovery codes: exatamente 8 (MFA_RECOVERY_CODE_COUNT) e cada um vale 1 vez."""
    member = _make_member(church_a)
    rc = RecoveryCodes.activate(member)

    codes = rc.generate_codes()
    assert len(codes) == 8  # config do projeto (default do allauth e 10)

    # Recarrega o wrapper a partir do registro persistido e consome 1 codigo.
    wrapper = Authenticator.objects.get(
        user=member, type=Authenticator.Type.RECOVERY_CODES
    ).wrap()
    assert wrapper.validate_code(codes[0]) is True
    # Mesmo codigo nao vale de novo (single-use).
    wrapper = Authenticator.objects.get(
        user=member, type=Authenticator.Type.RECOVERY_CODES
    ).wrap()
    assert wrapper.validate_code(codes[0]) is False
    # Outro codigo ainda intacto vale.
    assert wrapper.validate_code(codes[1]) is True


# --- 3. SecurityLog: so o TOTP conta como mfa_enabled/mfa_disabled (§222) ----


@pytest.mark.django_db(transaction=True)
def test_recovery_codes_added_does_not_emit_mfa_enabled(church_a):
    """Recovery codes auto-gerados disparam authenticator_added, mas NAO logam.

    Sao acessorios do TOTP, nao um novo fator — nosso handler ignora tudo que nao
    for TOTP para nao duplicar o evento `mfa_enabled`.
    """
    from allauth.mfa.signals import authenticator_added

    member = _make_member(church_a)
    rc_auth = Authenticator(
        user=member, type=Authenticator.Type.RECOVERY_CODES, data={}
    )
    with schema_context(church_a.schema_name):
        authenticator_added.send(
            sender=Authenticator, request=None, user=member, authenticator=rc_auth
        )
        logs = list(SecurityLog.objects.filter(event_type='mfa_enabled'))
    assert logs == []


@pytest.mark.django_db(transaction=True)
def test_recovery_codes_removed_does_not_emit_mfa_disabled(church_a):
    """Remocao de recovery codes dispara authenticator_removed, mas NAO loga.

    Simetrico ao caso de adicao: so a remocao do TOTP conta como `mfa_disabled`.
    """
    from allauth.mfa.signals import authenticator_removed

    member = _make_member(church_a)
    rc_auth = Authenticator(
        user=member, type=Authenticator.Type.RECOVERY_CODES, data={}
    )
    with schema_context(church_a.schema_name):
        authenticator_removed.send(
            sender=Authenticator, request=None, user=member, authenticator=rc_auth
        )
        logs = list(SecurityLog.objects.filter(event_type='mfa_disabled'))
    assert logs == []


@pytest.mark.django_db(transaction=True)
def test_totp_deactivation_emits_mfa_disabled_log(tenant_client, church_a):
    """Desativar o TOTP pela tela nativa dispara `SecurityLog('mfa_disabled')`."""
    member = _make_member(church_a)
    # Loga PRIMEIRO (sem MFA, login direto); so entao ativa o TOTP nesta sessao —
    # do contrario o login so com senha cairia no desafio 2FA e nao autenticaria.
    tenant_client.post(LOGIN_URL, {'login': member.email, 'password': GOOD_PASSWORD})
    TOTP.activate(member, generate_totp_secret())

    resp = tenant_client.post(DEACTIVATE_URL)
    assert resp.status_code == 302

    member.refresh_from_db()
    assert is_mfa_enabled(member, [Authenticator.Type.TOTP]) is False
    logs = _logs(church_a, event_type='mfa_disabled')
    assert len(logs) == 1
    assert logs[0].user_id == member.id
    assert logs[0].payload == {'method': 'totp'}


# --- 4. Pagina "Seguranca da conta" -----------------------------------------


@pytest.mark.django_db(transaction=True)
def test_account_security_page_reflects_mfa_status(tenant_client, church_a):
    """GET /contas/seguranca/: 200 e o status do MFA muda apos a ativacao."""
    member = _make_member(church_a)
    tenant_client.post(LOGIN_URL, {'login': member.email, 'password': GOOD_PASSWORD})

    resp = tenant_client.get(SECURITY_URL)
    assert resp.status_code == 200
    assert resp.context['mfa_enabled'] is False

    TOTP.activate(member, generate_totp_secret())
    resp = tenant_client.get(SECURITY_URL)
    assert resp.context['mfa_enabled'] is True


@pytest.mark.django_db(transaction=True)
def test_account_security_requires_login(tenant_client, church_a):
    """Sem login, a pagina de seguranca redireciona para o login (LoginRequired)."""
    resp = tenant_client.get(SECURITY_URL)
    assert resp.status_code == 302
    assert '/contas/login/' in resp.url
