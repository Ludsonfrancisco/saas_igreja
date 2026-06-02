"""Sprint 2 / Frente 4 — views de convite (RN-003a / P-ARQ-08 / RISK-001).

Espelha test_user_list_view.py: Client com HTTP_HOST do tenant para que o
TenantMiddleware resolva o schema; @pytest.mark.django_db(transaction=True) por
causa do DDL de criar Church; teardown que devolve o search_path ao public.

Cobre as quatro barreiras da frente:
- papel/login nas views de gestao (InviteListView/InviteCreateView): nao-Pastor
  -> 403; anonimo -> redirect para o login do allauth;
- criacao por Pastor: cria o Invite escopado na church do tenant e envia email;
- aceite PUBLICO (InviteAcceptView): GET renderiza o form sem login; token
  invalido/ja-aceito -> 404; cross-tenant -> 404; POST valido cria o User.

Email forcado para locmem (@override_settings) onde o envio e verificado — a
suite roda sob core.settings.dev (console backend), que nao popula mail.outbox.
"""

import pytest
from django.core import mail
from django.db import connection
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.models import Invite, User

GOOD_PASSWORD = 'Senha@123'
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'

INVITE_LIST_URL = '/configuracoes/convites/'
INVITE_CREATE_URL = '/configuracoes/convites/novo/'


@pytest.fixture
def tenant_client():
    """Client no host do tenant_a; restaura o public no teardown."""
    client = Client(HTTP_HOST='a.testserver')
    yield client
    connection.set_schema_to_public()


@pytest.fixture
def client_b():
    """Client no host do tenant_b (para o teste cross-tenant)."""
    client = Client(HTTP_HOST='b.testserver')
    yield client
    connection.set_schema_to_public()


def _make_user(church, email, roles):
    return User.objects.create_user(
        email=email, password=GOOD_PASSWORD, roles=roles, church=church
    )


def _accept_path(token):
    return f'/contas/convite/{token}/'


# --------------------------------------------------------------------------- #
# Barreira de papel / login nas views de gestao
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
def test_invite_list_requires_pastor(tenant_client, church_a):
    """Nao-Pastor -> 403; anonimo -> 302 para o login do allauth (/contas/login/)."""
    member = _make_user(church_a, 'membro@a.com', ['member', 'leader'])

    tenant_client.force_login(member)
    resp = tenant_client.get(INVITE_LIST_URL)
    assert resp.status_code == 403

    # Anonimo: redireciona para o login REAL do allauth, preservando ?next.
    tenant_client.logout()
    resp_anon = tenant_client.get(INVITE_LIST_URL)
    assert resp_anon.status_code == 302
    assert resp_anon.url.startswith('/contas/login/')
    assert '/accounts/login/' not in resp_anon.url


@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_create_by_pastor_creates_and_emails(tenant_client, church_a):
    """Pastor POST em /novo/ cria Invite escopado, envia 1 email e redireciona.

    Cobre o caminho feliz da criacao via view: form valido -> service ->
    Invite escopado em request.tenant + email enviado + redirect para a lista.
    """
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    tenant_client.force_login(pastor)
    mail.outbox.clear()

    resp = tenant_client.post(
        INVITE_CREATE_URL,
        {'email': 'convidado@a.com', 'roles': ['member', 'leader']},
    )

    # Redireciona para a lista de convites em caso de sucesso.
    assert resp.status_code == 302
    assert resp.url == reverse('accounts:invite_list')

    invite = Invite.objects.get(email='convidado@a.com')
    assert invite.church_id == church_a.id
    assert sorted(invite.roles) == ['leader', 'member']
    assert invite.invited_by_id == pastor.id

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ['convidado@a.com']


@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_create_duplicate_email_shows_form_error(tenant_client, church_a):
    """Email ja convidado nesta igreja: a view re-exibe o form com erro (200).

    Exercita o ramo de ValidationError -> form_invalid em InviteCreateView, em vez
    de estourar a colisao do unique_together como erro 500. Nenhum 2o convite e
    criado.
    """
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    Invite.objects.create(
        church=church_a,
        email='convidado@a.com',
        roles=['member'],
        invited_by=pastor,
        expires_at=_future(),
    )
    tenant_client.force_login(pastor)

    resp = tenant_client.post(
        INVITE_CREATE_URL,
        {'email': 'convidado@a.com', 'roles': ['leader']},
    )

    # Re-renderiza o form (nao redireciona) e nao cria um segundo convite.
    assert resp.status_code == 200
    assert Invite.objects.filter(church=church_a, email='convidado@a.com').count() == 1


# --------------------------------------------------------------------------- #
# Reenvio e cancelamento (POST-only, tenant-scoped, Pastor)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_resend_view_renews_and_emails(tenant_client, church_a):
    """POST em /reenviar/ regenera o token, reenvia email e redireciona para a lista."""
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    invite = Invite.objects.create(
        church=church_a,
        email='convidado@a.com',
        roles=['member'],
        invited_by=pastor,
        expires_at=_future(),
    )
    old_token = invite.token
    tenant_client.force_login(pastor)
    mail.outbox.clear()

    resp = tenant_client.post(
        reverse('accounts:invite_resend', kwargs={'pk': invite.pk})
    )

    assert resp.status_code == 302
    assert resp.url == reverse('accounts:invite_list')
    invite.refresh_from_db()
    assert invite.token != old_token  # link antigo invalidado
    assert len(mail.outbox) == 1


@pytest.mark.django_db(transaction=True)
def test_invite_resend_view_cross_tenant_404(client_b, church_a, church_b):
    """Pastor de B nao reenvia convite de A: get_object_or_404(church=tenant) -> 404."""
    pastor_a = _make_user(church_a, 'pastor@a.com', ['pastor'])
    pastor_b = _make_user(church_b, 'pastor@b.com', ['pastor'])
    invite = Invite.objects.create(
        church=church_a,
        email='convidado@a.com',
        roles=['member'],
        invited_by=pastor_a,
        expires_at=_future(),
    )
    client_b.force_login(pastor_b)

    resp = client_b.post(reverse('accounts:invite_resend', kwargs={'pk': invite.pk}))
    assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_invite_cancel_view_deletes_and_redirects(tenant_client, church_a):
    """POST em /cancelar/ apaga o convite (hard delete) e redireciona para a lista."""
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    invite = Invite.objects.create(
        church=church_a,
        email='convidado@a.com',
        roles=['member'],
        invited_by=pastor,
        expires_at=_future(),
    )
    pk = invite.pk
    tenant_client.force_login(pastor)

    resp = tenant_client.post(reverse('accounts:invite_cancel', kwargs={'pk': pk}))

    assert resp.status_code == 302
    assert resp.url == reverse('accounts:invite_list')
    assert not Invite.objects.filter(pk=pk).exists()


# --------------------------------------------------------------------------- #
# Aceite PUBLICO: GET
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_accept_view_public_get_renders_form(tenant_client, church_a):
    """GET no aceite (host do tenant) SEM login -> 200 com form.

    Token inexistente -> pagina de invalido com status 404. A view e PUBLICA
    (sem TenantRequiredMixin/LoginRequired), mas amarrada ao tenant resolvido.
    """
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    invite = Invite.objects.create(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor,
        expires_at=_future(),
    )

    # Publico: sem force_login.
    resp = tenant_client.get(_accept_path(invite.token))
    assert resp.status_code == 200
    assert 'form' in resp.context

    # Token inexistente -> pagina de invalido (404).
    import uuid

    resp_bad = tenant_client.get(_accept_path(uuid.uuid4()))
    assert resp_bad.status_code == 404


# --------------------------------------------------------------------------- #
# Aceite PUBLICO: POST cria User e e single-use
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_accept_view_post_creates_user(tenant_client, church_a):
    """POST valido cria o User e redireciona ao login; reusar o token -> 404."""
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    invite = Invite.objects.create(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor,
        expires_at=_future(),
    )

    resp = tenant_client.post(
        _accept_path(invite.token),
        {
            'first_name': 'Ana',
            'last_name': 'Souza',
            'password1': GOOD_PASSWORD,
            'password2': GOOD_PASSWORD,
        },
    )

    assert resp.status_code == 302
    assert resp.url == reverse('account_login')

    user = User.objects.get(email='novo@a.com')
    assert user.roles == ['member']
    assert user.church_id == church_a.id
    assert user.check_password(GOOD_PASSWORD) is True

    invite.refresh_from_db()
    assert invite.accepted_at is not None

    # Reusar o mesmo token (ja aceito) -> 404 (single-use).
    resp_again = tenant_client.get(_accept_path(invite.token))
    assert resp_again.status_code == 404


@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_accept_view_post_invalid_password_rerenders(tenant_client, church_a):
    """POST com senhas que nao coincidem: re-renderiza o form (200), sem criar User."""
    pastor = _make_user(church_a, 'pastor@a.com', ['pastor'])
    invite = Invite.objects.create(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor,
        expires_at=_future(),
    )

    resp = tenant_client.post(
        _accept_path(invite.token),
        {
            'password1': GOOD_PASSWORD,
            'password2': 'OutraSenha@1',
        },
    )

    assert resp.status_code == 200  # form invalido re-renderizado
    assert not User.objects.filter(email='novo@a.com').exists()
    invite.refresh_from_db()
    assert invite.accepted_at is None  # convite continua pendente


# --------------------------------------------------------------------------- #
# Aceite PUBLICO: barreira cross-tenant
# --------------------------------------------------------------------------- #
@pytest.mark.django_db(transaction=True)
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_invite_accept_cross_tenant_404(client_b, church_a, church_b):
    """Token de A acessado no host de B -> 404 (sem vazamento; RISK-001)."""
    pastor_a = _make_user(church_a, 'pastor@a.com', ['pastor'])
    invite = Invite.objects.create(
        church=church_a,
        email='novo@a.com',
        roles=['member'],
        invited_by=pastor_a,
        expires_at=_future(),
    )

    # Acessa o token de A pelo host de B.
    resp = client_b.get(_accept_path(invite.token))
    assert resp.status_code == 404

    # E o POST tambem nao cria conta cross-tenant.
    resp_post = client_b.post(
        _accept_path(invite.token),
        {'password1': GOOD_PASSWORD, 'password2': GOOD_PASSWORD},
    )
    assert resp_post.status_code == 404
    assert not User.objects.filter(email='novo@a.com').exists()


def _future():
    """expires_at no futuro (convite valido)."""
    from datetime import timedelta

    from django.utils import timezone

    return timezone.now() + timedelta(days=7)
