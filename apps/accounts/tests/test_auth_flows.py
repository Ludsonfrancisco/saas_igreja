"""Sprint 2 / Frente 2 — fluxos de autenticacao (SEC-02 / PRD §15.1).

Cobre login por email, reset de senha sem enumeracao, expiracao de token 24h e
o registro de SecurityLog para login_success / login_failure /
password_reset_requested / password_reset_completed.

Os fluxos de auth precisam rodar no schema de um TENANT para que o SecurityLog
persista (o helper tem guarda de schema public). Por isso usamos o client com
`HTTP_HOST='a.testserver'` (o Domain da fixture `church_a`) e
`@pytest.mark.django_db(transaction=True)` (criar Church dispara DDL).
"""

import pytest
from django.db import connection
from django.test import Client
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.core.models import SecurityLog

TENANT_HOST = 'a.testserver'
GOOD_PASSWORD = 'Senha@123'


@pytest.fixture
def tenant_client():
    """Client cujo Host resolve para o tenant_a (TenantMiddleware).

    Teardown: o TenantMiddleware deixa o `search_path` da connection de teste no
    schema do tenant apos a request; restauramos para o public para nao quebrar a
    criacao de Church de fixtures subsequentes ('Can't create tenant outside the
    public schema').
    """
    client = Client(HTTP_HOST=TENANT_HOST)
    yield client
    connection.set_schema_to_public()


@pytest.fixture
def member_a(church_a):
    """User membro do tenant A, com senha que passa na politica."""
    return User.objects.create_user(
        email='membro@a.com',
        password=GOOD_PASSWORD,
        roles=['member'],
        church=church_a,
    )


def _security_events(event_type):
    with schema_context('tenant_a'):
        return list(
            SecurityLog.objects.filter(tenant_id='tenant_a', event_type=event_type)
        )


@pytest.mark.django_db(transaction=True)
def test_login_email_only(tenant_client, member_a):
    """Login pelo formulario do allauth usando email + senha autentica o user."""
    resp = tenant_client.post(
        '/contas/login/',
        {'login': 'membro@a.com', 'password': GOOD_PASSWORD},
    )
    # Sucesso redireciona (302) para fora da pagina de login.
    assert resp.status_code == 302
    assert '_auth_user_id' in tenant_client.session


@pytest.mark.django_db(transaction=True)
def test_login_success_logged_in_security_log(tenant_client, member_a):
    tenant_client.post(
        '/contas/login/',
        {'login': 'membro@a.com', 'password': GOOD_PASSWORD},
    )
    events = _security_events('login_success')
    assert len(events) == 1
    assert events[0].user_id == member_a.id
    # Sem PII no payload (TENANT-07): so metadado de backend.
    assert events[0].payload == {'backend': 'email'}


@pytest.mark.django_db(transaction=True)
def test_login_wrong_password_does_not_leak_user_existence(tenant_client, member_a):
    """Senha errada (user existe) e email inexistente devem responder igual."""
    resp_existing = tenant_client.post(
        '/contas/login/',
        {'login': 'membro@a.com', 'password': 'ErradaTotal@9'},
    )
    resp_unknown = tenant_client.post(
        '/contas/login/',
        {'login': 'naoexiste@a.com', 'password': 'ErradaTotal@9'},
    )
    # Mesmo status e nenhuma sessao autenticada em ambos os casos.
    assert resp_existing.status_code == resp_unknown.status_code == 200
    assert '_auth_user_id' not in tenant_client.session
    # E a mensagem de erro nao deve revelar se o email existe.
    body_existing = resp_existing.content.decode().lower()
    body_unknown = resp_unknown.content.decode().lower()
    assert 'nao registrad' not in body_existing
    assert 'nao registrad' not in body_unknown


@pytest.mark.django_db(transaction=True)
def test_login_failure_logged_in_security_log(tenant_client, member_a):
    tenant_client.post(
        '/contas/login/',
        {'login': 'membro@a.com', 'password': 'ErradaTotal@9'},
    )
    events = _security_events('login_failure')
    assert len(events) >= 1
    # Falha nao atribui user_id (nao confirma existencia) e nao loga o email.
    assert events[0].user_id is None
    assert 'email' not in events[0].payload
    assert 'login' not in events[0].payload


@pytest.mark.django_db(transaction=True)
def test_password_reset_no_enumeration(tenant_client, member_a):
    """Reset para email existente e inexistente: mesma resposta (sem enumeracao)."""
    resp_existing = tenant_client.post(
        '/contas/password/reset/',
        {'email': 'membro@a.com'},
    )
    resp_unknown = tenant_client.post(
        '/contas/password/reset/',
        {'email': 'naoexiste@a.com'},
    )
    # allauth redireciona ambos para a mesma pagina "done" (302).
    assert resp_existing.status_code == resp_unknown.status_code == 302
    assert resp_existing.url == resp_unknown.url


@pytest.mark.django_db(transaction=True)
def test_password_reset_requested_logged_only_for_existing_user(
    tenant_client, member_a
):
    """O SecurityLog de reset solicitado so e gravado para usuario existente.

    Para email inexistente, o adapter nem e chamado (sem enumeracao) -> nenhum
    SecurityLog adicional; a resposta ao cliente continua identica (testada em
    test_password_reset_no_enumeration).
    """
    tenant_client.post('/contas/password/reset/', {'email': 'membro@a.com'})
    tenant_client.post('/contas/password/reset/', {'email': 'naoexiste@a.com'})

    events = _security_events('password_reset_requested')
    assert len(events) == 1
    assert events[0].user_id == member_a.id


@pytest.mark.django_db
def test_password_reset_token_expires_24h(settings):
    """PASSWORD_RESET_TIMEOUT = 86400s (24h): token valido < 24h, invalido depois.

    Verificamos (a) que o setting e exatamente 86400 (24h) e (b) o comportamento
    de expiracao do gerador do Django, que LE esse setting em tempo de checagem.
    Para o (b) geramos o token com um timeout minusculo e avancamos o relogio do
    gerador via `_now`, mantendo timezone-aware (o baseline interno do Django e
    naive, entao usamos um datetime naive coerente).
    """
    from datetime import datetime, timedelta

    from django.contrib.auth.tokens import PasswordResetTokenGenerator

    # (a) o valor de producao do token de reset e 24h.
    assert settings.PASSWORD_RESET_TIMEOUT == 86400

    user = User.objects.create_user(
        email='reset@a.com', password=GOOD_PASSWORD, roles=['member']
    )

    gen = PasswordResetTokenGenerator()
    token = gen.make_token(user)
    assert gen.check_token(user, token) is True

    # Gerador cujo "agora" esta 24h + 1s no futuro -> token expira. `_now` do
    # Django retorna naive; mantemos naive para casar com o baseline interno.
    class _FutureGen(PasswordResetTokenGenerator):
        def _now(self):
            return datetime.now() + timedelta(seconds=86401)

    assert _FutureGen().check_token(user, token) is False


@pytest.mark.django_db(transaction=True)
def test_password_reset_completed_logged_in_security_log(tenant_client, member_a):
    """Reset de senha de ponta a ponta dispara SecurityLog 'password_reset_completed'.

    Em vez de forjar a URL/token do allauth (formato proprio, uidb36 + chave),
    seguimos o fluxo real: pedimos o reset, extraimos a URL do email enviado
    (backend de console -> mail.outbox), abrimos a pagina (GET, que redireciona
    para a URL com o token 'set-password' na sessao) e postamos a nova senha.
    """
    import re

    from django.core import mail

    mail.outbox = []
    tenant_client.post('/contas/password/reset/', {'email': 'membro@a.com'})
    assert len(mail.outbox) == 1

    body = mail.outbox[0].body
    match = re.search(r'/contas/password/reset/key/\S+', body)
    assert match, f'URL de reset nao encontrada no email: {body!r}'
    reset_url = match.group(0).rstrip('.').strip()

    # GET redireciona para a URL com o token trocado por 'set-password'.
    get_resp = tenant_client.get(reset_url, follow=True)
    assert get_resp.status_code == 200
    post_url = get_resp.redirect_chain[-1][0] if get_resp.redirect_chain else reset_url

    new_password = 'NovaSenha@2024'
    tenant_client.post(
        post_url,
        {'password1': new_password, 'password2': new_password},
        follow=True,
    )

    events = _security_events('password_reset_completed')
    assert len(events) == 1
    assert events[0].user_id == member_a.id


@pytest.mark.django_db(transaction=True)
def test_signup_is_closed(tenant_client, church_a):
    """Cadastro publico fechado: entrada apenas via Invite (AccountAdapter).

    O adapter retorna is_open_for_signup -> False; o allauth responde a view de
    signup como fechada (nao cria usuario). Garante que ninguem se auto-registra
    fora do fluxo de convite.
    """
    before = User.objects.count()
    resp = tenant_client.post(
        '/contas/signup/',
        {
            'email': 'intruso@a.com',
            'password1': 'Senha@123',
            'password2': 'Senha@123',
        },
    )
    # allauth renderiza/redireciona a pagina de "signup fechado"; nunca um 302 de
    # sucesso para a area logada. O essencial: nenhum usuario novo e criado.
    assert resp.status_code in (200, 302, 403)
    assert User.objects.count() == before
    assert not User.objects.filter(email='intruso@a.com').exists()
